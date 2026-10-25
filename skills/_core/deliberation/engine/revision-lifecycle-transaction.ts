import { randomUUID } from 'node:crypto';
import { copyFile, lstat, mkdir, readFile, realpath, rename, rm, writeFile } from 'node:fs/promises';
import { dirname, join, relative, sep } from 'node:path';
import { pendingAuditInventoryDigest, withActivePendingAuditOperation, withRevisionLifecycleMutationLock } from './consistency-audit.js';
import { runProposalDeliberationSelfAudit } from './self-audit.js';
import {
 assertWithdrawalOperationId,
 discoverManagedRevision,
 findWithdrawal,
 latestManagedFilename,
 lifecycleInventoryDigest,
 normalizeWithdrawalReason,
 restoreStagingPath,
 withdrawalOperationPath,
 withdrawalRootPath,
 withdrawalStagingPath,
 type LifecycleArtifactRecord,
 type ManagedRevisionDiscovery,
} from './revision-lifecycle-store.js';
import { PENDING_AUDIT_LEASE_MS, sha256, type PendingAuditArtifact, type PendingAuditContext, type RevisionLifecycleOperation, type RevisionLifecycleResult, type RevisionWithdrawalMetadata } from './types.js';
import { artifact as artifactConfig, withdrawnMarkerPath } from './artifact-naming.js';

type LifecycleFs={
 copyFile:typeof copyFile;
 lstat:typeof lstat;
 mkdir:typeof mkdir;
 readFile:typeof readFile;
 rename:typeof rename;
 rm:typeof rm;
 writeFile:typeof writeFile;
};
export type RevisionLifecycleTransactionDependencies={
 fs?:LifecycleFs;
 now?:()=>Date;
 newOperationId?:()=>string;
 selfAudit?:typeof runProposalDeliberationSelfAudit;
 beforeMarkerFinalize?:(operation:RevisionLifecycleOperation)=>Promise<void>|void;
};
const defaultFs:LifecycleFs={copyFile,lstat,mkdir,readFile,rename,rm,writeFile};

function blocked(operation:RevisionLifecycleOperation,warning:string):RevisionLifecycleResult {
 return {status:'blocked',operation,withdrawnFilename:null,restoredLatestFilename:null,artifactCount:0,backupLocation:null,auditStatus:'NOT_RUN',selfAuditStatus:'NOT_RUN',warnings:[warning]};
}
function backupLocation(root:string,operationDirectory:string) { return relative(root,operationDirectory).split(sep).join('/'); }
function markerRelative(operationId:string) { return withdrawnMarkerPath(operationId); }
function immutableAt(operationDirectory:string,artifact:LifecycleArtifactRecord) { return join(operationDirectory,artifact.quarantineRelativePath); }
function publicAt(root:string,artifact:LifecycleArtifactRecord) { return join(root,artifact.publicRelativePath); }
function publicBackupAt(operationDirectory:string,artifact:LifecycleArtifactRecord) { return join(operationDirectory,'public-backup',artifact.publicRelativePath); }
function errorCode(error:unknown) { return error instanceof Error?error.message:String(error); }

async function exists(fs:LifecycleFs,path:string) { try { await fs.lstat(path); return true; } catch { return false; } }
async function requireExactDirectory(fs:LifecycleFs,path:string) {
 const info=await fs.lstat(path);
 if (!info.isDirectory()||info.isSymbolicLink()||(await realpath(path))!==path) throw new Error('UNSAFE_LIFECYCLE_DIRECTORY');
}
async function prepareWithdrawalRoot(fs:LifecycleFs,root:string) {
 await requireExactDirectory(fs,join(root,artifactConfig.sidecarRoot));
 const withdrawn=withdrawalRootPath(root);
 if (!await exists(fs,withdrawn)) await fs.mkdir(withdrawn,{recursive:false});
 await requireExactDirectory(fs,withdrawn);
}
async function requirePublicParents(fs:LifecycleFs,root:string,artifacts:LifecycleArtifactRecord[]) {
 for (const parent of new Set(artifacts.map(artifact=>dirname(publicAt(root,artifact))))) await requireExactDirectory(fs,parent);
}
function temporaryPath(path:string) { return `${path}.${process.pid}.${Math.random().toString(36).slice(2)}.tmp`; }
async function copyVerified(fs:LifecycleFs,source:string,destination:string,expectedSha:string,ownedTemporaries?:Set<string>) {
 await fs.mkdir(dirname(destination),{recursive:true});
 const temp=temporaryPath(destination);
 ownedTemporaries?.add(temp);
 await fs.copyFile(source,temp);
 if (sha256(await fs.readFile(temp))!==expectedSha) throw new Error('STAGED_ARTIFACT_SHA_MISMATCH');
 await fs.rename(temp,destination);
 ownedTemporaries?.delete(temp);
}
async function writeAtomic(fs:LifecycleFs,path:string,value:string|Buffer,ownedTemporaries?:Set<string>) {
 await fs.mkdir(dirname(path),{recursive:true});
 const temp=temporaryPath(path);
 ownedTemporaries?.add(temp);
 await fs.writeFile(temp,value);
 await fs.rename(temp,path);
 ownedTemporaries?.delete(temp);
}
async function writeJsonAtomic(fs:LifecycleFs,path:string,value:unknown,ownedTemporaries?:Set<string>) {
 await writeAtomic(fs,path,JSON.stringify(value),ownedTemporaries);
}
function pendingArtifacts(artifacts:LifecycleArtifactRecord[],expectedLocation:'quarantine-public-backup'|'public'):PendingAuditArtifact[] {
 return artifacts.map(({publicRelativePath,sha256})=>({publicRelativePath,sha256,expectedLocation}));
}
function completeAudit(selfAudit:any) {
 const consistency=selfAudit?.checks?.find((check:any)=>check?.id==='consistency')?.evidence;
 if (selfAudit?.status!=='PASS'||consistency?.status!=='PASS') throw new Error('LIFECYCLE_AUDIT_FAILED');
 return {auditStatus:'PASS' as const,selfAuditStatus:'PASS' as const};
}

export class RevisionLifecycleTransaction {
 private readonly fs:LifecycleFs;
 private readonly now:()=>Date;
 private readonly newOperationId:()=>string;
 private readonly selfAudit:typeof runProposalDeliberationSelfAudit;
 constructor(private readonly projectRoot:string,private readonly dependencies:RevisionLifecycleTransactionDependencies={}) {
  this.fs=dependencies.fs??defaultFs;
  this.now=dependencies.now??(()=>new Date());
  this.newOperationId=dependencies.newOperationId??randomUUID;
  this.selfAudit=dependencies.selfAudit??runProposalDeliberationSelfAudit;
 }

 async withdraw(input:{filename:string;reason?:string;operationId?:string}):Promise<RevisionLifecycleResult> {
  const operation:RevisionLifecycleOperation='WITHDRAW_REVISION';
  let operationId:string;
  try { operationId=assertWithdrawalOperationId(input.operationId??this.newOperationId()); }
  catch (error) { return blocked(operation,errorCode(error)); }
  try {
   const initial=await discoverManagedRevision({projectRoot:this.projectRoot,filename:input.filename});
   const reason=normalizeWithdrawalReason(input.reason);
   return await withRevisionLifecycleMutationLock({projectRoot:initial.root,operationId,filename:initial.filename},owner=>this.withdrawLocked(initial,operationId,reason,owner));
  } catch (error) { return blocked(operation,errorCode(error)); }
 }

 private async withdrawLocked(initial:ManagedRevisionDiscovery,operationId:string,reason:string,owner:any):Promise<RevisionLifecycleResult> {
  const operation:RevisionLifecycleOperation='WITHDRAW_REVISION';
  const current=await discoverManagedRevision({projectRoot:initial.root,filename:initial.filename});
  if (JSON.stringify(current.artifacts.map(a=>a.sha256))!==JSON.stringify(initial.artifacts.map(a=>a.sha256))) throw new Error('REVISION_CHANGED_BEFORE_WITHDRAWAL');
  const root=current.root;
  const staging=withdrawalStagingPath(root,operationId);
  const final=withdrawalOperationPath(root,operationId);
  if (await exists(this.fs,staging)||await exists(this.fs,final)) throw new Error('WITHDRAWAL_OPERATION_ALREADY_EXISTS');
  const moved:LifecycleArtifactRecord[]=[];
  let createdFinal=false;
  try {
   await prepareWithdrawalRoot(this.fs,root);
   await this.fs.mkdir(staging,{recursive:false});
   for (const artifact of current.artifacts) await copyVerified(this.fs,artifact.absolutePath,immutableAt(staging,artifact),artifact.sha256);
   const metadata:RevisionWithdrawalMetadata={
    schemaVersion:'1',operationId,operationTimestamp:this.now().toISOString(),requestedFilename:current.filename,revision:current.revision,
    documentSha256:current.documentSha256,sourceRevision:current.sourceRevision,sourceFilename:current.sourceFilename,reason,
    artifacts:current.artifacts.map(({publicRelativePath,quarantineRelativePath,sha256})=>({publicRelativePath,quarantineRelativePath,sha256})),
    inventoryDigest:lifecycleInventoryDigest(current.artifacts),preWithdrawalLatestFilename:current.latestFilename,
   };
   await writeJsonAtomic(this.fs,join(staging,'metadata.json'),metadata);
   for (const artifact of current.artifacts) if (sha256(await this.fs.readFile(immutableAt(staging,artifact)))!==artifact.sha256) throw new Error('STAGED_ARTIFACT_SHA_MISMATCH');
   await this.fs.rename(staging,final);
   createdFinal=true;
   for (const artifact of current.artifacts) {
    const destination=publicBackupAt(final,artifact);
    await this.fs.mkdir(dirname(destination),{recursive:true});
    await this.fs.rename(publicAt(root,artifact),destination);
    moved.push(artifact);
   }
   const latest=await latestManagedFilename(root);
   if (!latest||latest===current.filename) throw new Error('LATEST_VIEW_MISMATCH_AFTER_WITHDRAWAL');
   const auditArtifacts=pendingArtifacts(current.artifacts,'quarantine-public-backup');
   const inventoryDigest=pendingAuditInventoryDigest(auditArtifacts);
   if (inventoryDigest!==metadata.inventoryDigest) throw new Error('WITHDRAWAL_INVENTORY_DIGEST_MISMATCH');
   const createdAt=this.now();
   const expiresAt=new Date(createdAt.getTime()+PENDING_AUDIT_LEASE_MS).toISOString();
   const context:PendingAuditContext={operationType:operation,operationId,pendingAudit:true,phase:'WITHDRAW_PUBLIC_ARTIFACTS_MOVED',temporarilyMovedArtifacts:auditArtifacts,expectedMarker:{relativePath:markerRelative(operationId),state:'PENDING_AUDIT',inventoryDigest,expiresAt}};
   const pendingMarker={operationType:operation,operationId,state:'PENDING_AUDIT',phase:context.phase,temporarilyMovedArtifacts:auditArtifacts,inventoryDigest,createdAt:createdAt.toISOString(),expiresAt};
   const markerPath=join(final,'audit-marker.json');
   await writeJsonAtomic(this.fs,markerPath,pendingMarker);
   const selfAudit=await withActivePendingAuditOperation({projectRoot:root,auditContext:context,lifecycleLockOwner:owner},()=>this.selfAudit({projectRoot:root,auditContext:context}));
   const statuses=completeAudit(selfAudit);
   await this.dependencies.beforeMarkerFinalize?.(operation);
   await writeJsonAtomic(this.fs,markerPath,{...pendingMarker,state:'COMMITTED',...statuses,committedAt:this.now().toISOString()});
   return {status:'withdrawn',operation,withdrawnFilename:current.filename,restoredLatestFilename:latest??null,artifactCount:current.artifacts.length,backupLocation:backupLocation(root,final),...statuses,warnings:[]};
  } catch (error) {
   const rollbackWarnings:string[]=[];
   for (const artifact of [...moved].reverse()) {
    try { await this.fs.mkdir(dirname(publicAt(root,artifact)),{recursive:true}); await this.fs.rename(publicBackupAt(final,artifact),publicAt(root,artifact)); }
    catch { rollbackWarnings.push(`ROLLBACK_MOVE_FAILED:${artifact.publicRelativePath}`); }
   }
   try { await this.fs.rm(staging,{recursive:true,force:true}); } catch { rollbackWarnings.push('ROLLBACK_STAGING_CLEANUP_FAILED'); }
   if (createdFinal) try { await this.fs.rm(final,{recursive:true,force:true}); } catch { rollbackWarnings.push('ROLLBACK_QUARANTINE_CLEANUP_FAILED'); }
   for (const artifact of current.artifacts) {
    try { if (sha256(await this.fs.readFile(publicAt(root,artifact)))!==artifact.sha256) rollbackWarnings.push(`ROLLBACK_SHA_MISMATCH:${artifact.publicRelativePath}`); }
    catch { rollbackWarnings.push(`ROLLBACK_ARTIFACT_MISSING:${artifact.publicRelativePath}`); }
   }
   try { if (await latestManagedFilename(root)!==current.latestFilename) rollbackWarnings.push('ROLLBACK_LATEST_MISMATCH'); }
   catch { rollbackWarnings.push('ROLLBACK_LATEST_UNREADABLE'); }
   if (rollbackWarnings.length) throw new Error(`WITHDRAWAL_ROLLBACK_INCOMPLETE:${rollbackWarnings.join(',')}`);
   throw error;
  }
 }

 async restore(input:{operationId?:string;filename?:string}):Promise<RevisionLifecycleResult> {
  const operation:RevisionLifecycleOperation='RESTORE_WITHDRAWN_REVISION';
  try {
   const initial=await findWithdrawal({projectRoot:this.projectRoot,operationId:input.operationId,filename:input.filename});
   return await withRevisionLifecycleMutationLock({projectRoot:initial.root,operationId:initial.metadata.operationId,filename:initial.metadata.requestedFilename},owner=>this.restoreLocked(initial.metadata.operationId,initial.metadata.requestedFilename,owner));
  } catch (error) { return blocked(operation,errorCode(error)); }
 }

 private async restoreLocked(operationId:string,filename:string,owner:any):Promise<RevisionLifecycleResult> {
  const operation:RevisionLifecycleOperation='RESTORE_WITHDRAWN_REVISION';
  const withdrawal=await findWithdrawal({projectRoot:this.projectRoot,operationId,filename});
  const {root,operationDirectory,metadata,artifacts}=withdrawal;
  const staging=restoreStagingPath(root,operationId);
  const markerPath=join(operationDirectory,'audit-marker.json');
  const originalMarkerBytes=await this.fs.readFile(markerPath);
  const publicMoves:LifecycleArtifactRecord[]=[];
  const ownedTemporaries=new Set<string>();
  const preLatest=await latestManagedFilename(root);
  await prepareWithdrawalRoot(this.fs,root);
  await requirePublicParents(this.fs,root,artifacts);
  for (const artifact of artifacts) if (await exists(this.fs,publicAt(root,artifact))) throw new Error('RESTORE_PUBLIC_DESTINATION_EXISTS');
  if (await exists(this.fs,staging)) throw new Error('RESTORE_STAGING_ALREADY_EXISTS');
  try {
   await this.fs.mkdir(staging,{recursive:false});
   for (const artifact of artifacts) await copyVerified(this.fs,immutableAt(operationDirectory,artifact),join(staging,artifact.publicRelativePath),artifact.sha256,ownedTemporaries);
   for (const artifact of artifacts) {
    const source=join(staging,artifact.publicRelativePath);
    const destination=publicAt(root,artifact);
    await this.fs.mkdir(dirname(destination),{recursive:true});
    await this.fs.rename(source,destination);
    publicMoves.push(artifact);
   }
   await this.fs.rm(staging,{recursive:true,force:true});
   const latest=await latestManagedFilename(root);
   if (!latest) throw new Error('LATEST_VIEW_MISMATCH_AFTER_RESTORE');
   const auditArtifacts=pendingArtifacts(artifacts,'public');
   const inventoryDigest=pendingAuditInventoryDigest(auditArtifacts);
   if (inventoryDigest!==metadata.inventoryDigest) throw new Error('RESTORE_INVENTORY_DIGEST_MISMATCH');
   const createdAt=this.now();
   const expiresAt=new Date(createdAt.getTime()+PENDING_AUDIT_LEASE_MS).toISOString();
   const context:PendingAuditContext={operationType:operation,operationId,pendingAudit:true,phase:'RESTORE_PUBLIC_ARTIFACTS_MOVED',temporarilyMovedArtifacts:auditArtifacts,expectedMarker:{relativePath:markerRelative(operationId),state:'PENDING_AUDIT',inventoryDigest,expiresAt}};
   const pendingMarker={operationType:operation,operationId,state:'PENDING_AUDIT',phase:context.phase,temporarilyMovedArtifacts:auditArtifacts,inventoryDigest,createdAt:createdAt.toISOString(),expiresAt};
   await writeJsonAtomic(this.fs,markerPath,pendingMarker,ownedTemporaries);
   const selfAudit=await withActivePendingAuditOperation({projectRoot:root,auditContext:context,lifecycleLockOwner:owner},()=>this.selfAudit({projectRoot:root,auditContext:context}));
   const statuses=completeAudit(selfAudit);
   await this.dependencies.beforeMarkerFinalize?.(operation);
   await writeJsonAtomic(this.fs,markerPath,{...pendingMarker,state:'COMMITTED',...statuses,committedAt:this.now().toISOString()},ownedTemporaries);
   return {status:'restored',operation,withdrawnFilename:metadata.requestedFilename,restoredLatestFilename:latest??null,artifactCount:artifacts.length,backupLocation:backupLocation(root,operationDirectory),...statuses,warnings:[]};
  } catch (error) {
   const rollbackWarnings:string[]=[];
   for (const artifact of [...publicMoves].reverse()) {
    try {
     const destination=join(staging,artifact.publicRelativePath);
     await this.fs.mkdir(dirname(destination),{recursive:true});
     await this.fs.rename(publicAt(root,artifact),destination);
    } catch { rollbackWarnings.push(`RESTORE_ROLLBACK_MOVE_FAILED:${artifact.publicRelativePath}`); }
   }
   try { await this.fs.rm(staging,{recursive:true,force:true}); } catch { rollbackWarnings.push('RESTORE_ROLLBACK_STAGING_CLEANUP_FAILED'); }
   try { await writeAtomic(this.fs,markerPath,originalMarkerBytes,ownedTemporaries); }
   catch { rollbackWarnings.push('RESTORE_ROLLBACK_MARKER_RESTORE_FAILED'); }
   for (const temp of [...ownedTemporaries]) {
    try { await this.fs.rm(temp,{force:true}); ownedTemporaries.delete(temp); }
    catch {
     const category=temp.startsWith(`${markerPath}.`)?'audit-marker':temp.startsWith(`${staging}${sep}`)?'staged-artifact':'unknown';
     rollbackWarnings.push(`RESTORE_ROLLBACK_TEMP_CLEANUP_FAILED:${category}`);
    }
   }
   try { if (!(await this.fs.readFile(markerPath)).equals(originalMarkerBytes)) rollbackWarnings.push('RESTORE_ROLLBACK_MARKER_MISMATCH'); }
   catch { rollbackWarnings.push('RESTORE_ROLLBACK_MARKER_MISSING'); }
   for (const artifact of artifacts) if (await exists(this.fs,publicAt(root,artifact))) rollbackWarnings.push(`RESTORE_ROLLBACK_PUBLIC_ARTIFACT:${artifact.publicRelativePath}`);
   try { if (await latestManagedFilename(root)!==preLatest) rollbackWarnings.push('RESTORE_ROLLBACK_LATEST_MISMATCH'); }
   catch { rollbackWarnings.push('RESTORE_ROLLBACK_LATEST_UNREADABLE'); }
   for (const artifact of artifacts) {
    try { if (sha256(await this.fs.readFile(immutableAt(operationDirectory,artifact)))!==artifact.sha256) rollbackWarnings.push(`RESTORE_QUARANTINE_SHA_MISMATCH:${artifact.publicRelativePath}`); }
    catch { rollbackWarnings.push(`RESTORE_QUARANTINE_ARTIFACT_MISSING:${artifact.publicRelativePath}`); }
   }
   if (rollbackWarnings.length) throw new Error(`RESTORE_FAILED:${errorCode(error)};RESTORE_ROLLBACK_INCOMPLETE:${rollbackWarnings.join(',')}`);
   throw error;
  }
 }
}

export function createFaultInjectingLifecycleFs(input:{failAtMove?:number;failAtCopy?:number}):LifecycleFs {
 let moves=0,copies=0;
 return {
  ...defaultFs,
  async copyFile(...args:Parameters<typeof copyFile>) { copies++; if (copies===input.failAtCopy) throw new Error('INJECTED_COPY_FAILURE'); return copyFile(...args); },
  async rename(...args:Parameters<typeof rename>) { moves++; if (moves===input.failAtMove) throw new Error('INJECTED_MOVE_FAILURE'); return rename(...args); },
 };
}
