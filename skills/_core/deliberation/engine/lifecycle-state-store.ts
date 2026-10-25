import { mkdir, readFile, readdir, rename, rm, writeFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
import { sha256, type BaseDocument, type LifecycleRevision, type LifecycleTransitionEvidence, type WithdrawalRecord, type WorkspaceLifecycleState } from './types.js';
import { artifact as artifactConfig } from './artifact-naming.js';

export type LifecycleFs={mkdir:typeof mkdir;readFile:typeof readFile;readdir:typeof readdir;rename:typeof rename;rm:typeof rm;writeFile:typeof writeFile};
export type LifecycleStateStoreDependencies={fs?:LifecycleFs;now?:()=>Date;newId?:(kind:string)=>string;hash?:(content:string|Buffer)=>string;beforeCommitMarker?:(transition:LifecycleTransitionEvidence)=>Promise<void>|void;afterCommitMarker?:(transition:LifecycleTransitionEvidence)=>Promise<void>|void};
const defaultFs:LifecycleFs={mkdir,readFile,readdir,rename,rm,writeFile};
const schemaVersion='lifecycle-v1' as const;
const safeId=/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/;

export type StoredRequest={schemaVersion:typeof schemaVersion;requestId:string;workspaceId:string;fingerprint:string;transitionId:string};
export type StoredResult={schemaVersion:typeof schemaVersion;requestId:string;fingerprint:string;value:any;transitionId:string};
type TransitionDraft={transition:LifecycleTransitionEvidence;records:Array<{path:string;value:unknown}>;contents:Array<{hash:string;content:string}>;request?:StoredRequest;result?:StoredResult;inventory?:WorkspaceLifecycleState};

function parseJson(bytes:Buffer,code:string) { try { return JSON.parse(bytes.toString('utf8')); } catch { throw new Error(code); } }
function validateId(value:string,code='INVALID_LIFECYCLE_ID') { if(typeof value!=='string'||!safeId.test(value)) throw new Error(code); return value; }
function canonical(value:unknown) { return JSON.stringify(value); }

export class LifecycleStateStore {
 readonly root:string;
 private readonly fs:LifecycleFs;
 private readonly now:()=>Date;
 private readonly newId:(kind:string)=>string;
 readonly hash:(content:string|Buffer)=>string;
 private readonly beforeCommitMarker?:LifecycleStateStoreDependencies['beforeCommitMarker'];
 private readonly afterCommitMarker?:LifecycleStateStoreDependencies['afterCommitMarker'];
 constructor(projectRoot:string,dependencies:LifecycleStateStoreDependencies={}) {
  this.root=join(resolve(projectRoot),artifactConfig.sidecarRoot,'lifecycle','v1');
  this.fs=dependencies.fs??defaultFs; this.now=dependencies.now??(()=>new Date()); this.newId=dependencies.newId??(()=>randomUUID()); this.hash=dependencies.hash??sha256;
  this.beforeCommitMarker=dependencies.beforeCommitMarker; this.afterCommitMarker=dependencies.afterCommitMarker;
 }
 path(...parts:string[]) { return join(this.root,...parts); }
 nextId(kind:string) { return validateId(this.newId(kind)); }
 timestamp() { return this.now().toISOString(); }
 async ensureLayout() { for(const directory of ['bases','contents','revisions','withdrawals','requests','results','transitions','inventory','staging']) await this.fs.mkdir(this.path(directory),{recursive:true}); }
 async readJson(path:string,missingCode='LIFECYCLE_RECORD_MISSING'):Promise<any|undefined> { try{return parseJson(await this.fs.readFile(path),missingCode);}catch(error){if((error as any)?.code==='ENOENT')return undefined;throw error;} }
 async listJson(directory:string):Promise<Array<{filename:string;value:any}>> { try { const entries=await this.fs.readdir(this.path(directory),{withFileTypes:true}); const values=[] as Array<{filename:string;value:any}>; for(const entry of entries){if(!entry.isFile()||!entry.name.endsWith('.json'))continue; values.push({filename:entry.name,value:await this.readJson(this.path(directory,entry.name))});} return values; } catch(error){if((error as any)?.code==='ENOENT')return [];throw error;} }
 async readContent(hash:string) { validateId(hash,'INVALID_CONTENT_HASH'); try{return (await this.fs.readFile(this.path('contents',hash))).toString('utf8');}catch(error){if((error as any)?.code==='ENOENT')return undefined;throw error;} }
 async readCommittedTransition(transitionId:string) { return this.readJson(this.path('transitions',`${validateId(transitionId)}.json`)); }
 async readResult(requestId:string) { return this.readJson(this.path('results',`${validateId(requestId)}.json`)); }
 async allCommittedTransitions(workspaceId:string):Promise<LifecycleTransitionEvidence[]> {
  const rows=await this.listJson('transitions'); const seen=new Set<string>(); const result:LifecycleTransitionEvidence[]=[];
  for(const {filename,value} of rows) {
   if(!value||value.schemaVersion!==schemaVersion||value.outcome!=='COMMITTED'||typeof value.transitionId!=='string'||filename!==`${value.transitionId}.json`) throw new Error('LIFECYCLE_INVENTORY_INCONSISTENT');
   if(seen.has(value.transitionId)||!Number.isInteger(value.sequence)||value.sequence<1) throw new Error('LIFECYCLE_INVENTORY_INCONSISTENT'); seen.add(value.transitionId);
   if(value.workspaceId===workspaceId) result.push(value);
  }
  const sequences=new Set<number>(); for(const item of result){if(sequences.has(item.sequence))throw new Error('LIFECYCLE_INVENTORY_INCONSISTENT');sequences.add(item.sequence);}
  return result.sort((a,b)=>a.sequence-b.sequence||a.transitionId.localeCompare(b.transitionId));
 }
 async nextSequence(workspaceId:string) { const transitions=await this.allCommittedTransitions(workspaceId); return (transitions.at(-1)?.sequence??0)+1; }
 private async writeNew(path:string,value:string|Buffer) { const existing=await this.readJson(path,'MALFORMED_LIFECYCLE_RECORD'); if(existing!==undefined){if(typeof value==='string'&&canonical(existing)===value)return; throw new Error('LIFECYCLE_RECORD_CONFLICT');} await this.fs.mkdir(join(path,'..'),{recursive:true}); const temporary=`${path}.${process.pid}.${Math.random().toString(36).slice(2)}.tmp`; await this.fs.writeFile(temporary,value); await this.fs.rename(temporary,path); }
 private async writeContent(hash:string,content:string) { const path=this.path('contents',hash); try { const existing=await this.fs.readFile(path,'utf8'); if(existing!==content) throw new Error('SOURCE_CONTENT_HASH_MISMATCH'); return; } catch(error) { if((error as any)?.code!=='ENOENT') throw error; } await this.fs.writeFile(path,content); }
 async commit(draft:TransitionDraft) {
  await this.ensureLayout(); const {transition}=draft; validateId(transition.transitionId); const staging=this.path('staging',transition.transitionId);
  await this.fs.mkdir(staging,{recursive:false});
  try {
   await this.fs.writeFile(join(staging,'manifest.json'),canonical({schemaVersion,transition,records:draft.records.map(item=>item.path),contents:draft.contents.map(item=>item.hash)}));
   await this.beforeCommitMarker?.(transition);
   for(const content of draft.contents){if(this.hash(content.content)!==content.hash)throw new Error('SOURCE_CONTENT_HASH_MISMATCH');await this.writeContent(content.hash,content.content);}
   for(const record of draft.records)await this.writeNew(this.path(record.path),canonical(record.value));
   if(draft.request)await this.writeNew(this.path('requests',`${draft.request.requestId}.json`),canonical(draft.request));
   if(draft.result)await this.writeNew(this.path('results',`${draft.result.requestId}.json`),canonical(draft.result));
   await this.writeNew(this.path('transitions',`${transition.transitionId}.json`),canonical(transition));
   await this.afterCommitMarker?.(transition);
   if(draft.inventory)await this.writeNew(this.path('inventory',`${draft.inventory.workspaceId}.json`),canonical(draft.inventory));
  } finally { await this.fs.rm(staging,{recursive:true,force:true}); }
 }
 async repairInventory(inventory:WorkspaceLifecycleState) { await this.ensureLayout(); const path=this.path('inventory',`${inventory.workspaceId}.json`); await this.fs.rm(path,{force:true}); await this.writeNew(path,canonical(inventory)); }
 async durableRecords() { return {bases:await this.listJson('bases'),revisions:await this.listJson('revisions'),withdrawals:await this.listJson('withdrawals')}; }
 async hasAuthorityRecords(workspaceId?:string) {
  const records=await Promise.all(['bases','revisions','withdrawals','requests','results','transitions','inventory'].map(directory=>this.listJson(directory)));
  return records.some(rows=>rows.some(({value})=>workspaceId===undefined||value?.workspaceId===workspaceId));
 }
}

export function lifecycleRecordPaths(input:{base?:BaseDocument;revision?:LifecycleRevision;withdrawal?:WithdrawalRecord}) { const paths:string[]=[]; if(input.base)paths.push(`bases/${input.base.baseDocumentId}.json`); if(input.revision)paths.push(`revisions/${input.revision.revisionId}.json`); if(input.withdrawal)paths.push(`withdrawals/${input.withdrawal.withdrawalId}.json`); return paths; }
