import { lstat, readdir, readFile, realpath } from 'node:fs/promises';
import { basename, isAbsolute, join, relative, resolve, sep } from 'node:path';
import { derivedStatePath, receiptPath, validateStoredState } from './derived-state-store.js';
import { PARSER_VERSION, sha256, type BaseDocument, type LifecycleRevision, type RevisionLifecycleArtifact, type RevisionWithdrawalMetadata, type WithdrawalRecord } from './types.js';
import { LifecycleService } from './lifecycle-service.js';
import { artifact as artifactConfig, managedRevisionFilename, parseManagedRevision, publicRelativePaths, strictManagedRevision, strictRevisionLabel } from './artifact-naming.js';

const MANAGED=strictManagedRevision;
const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const SHA=/^[0-9a-f]{64}$/;
// The marker comes from the profile, like every other site in core. It was a literal
// here, justified by a Python cross-language guard that read THIS FILE by regex as the
// canonical source of truth -- a choice of where the guard looks, not a constraint: the
// profile's artifact config was already in scope (`artifactConfig`, above). The copy cost
// behaviour, not tidiness: `markerOwned` recognition compared against the literal while
// the rest of the engine recognised through the profile, so a domain declaring its own
// marker got an inventory holding a managed revision while nothing was the latest, and
// no decision tree has a branch for that. The guard now reads the profile's own
// declaration, which is what both languages actually have to agree about.
const MARKER=Buffer.from(artifactConfig.marker);
const METADATA_KEYS=['schemaVersion','operationId','operationTimestamp','requestedFilename','revision','documentSha256','sourceRevision','sourceFilename','reason','artifacts','inventoryDigest','preWithdrawalLatestFilename'];

export type ManagedRevisionIdentity={filename:string;lineage:string;revision:string;revisionNumber:number;sourceFilename:string;sourceRevision:string};
export type LifecycleArtifactRecord=RevisionLifecycleArtifact&{absolutePath:string;bytes:Buffer};
export type ManagedRevisionDiscovery=ManagedRevisionIdentity&{
 root:string;
 documentSha256:string;
 state:any;
 receipt:any;
 artifacts:LifecycleArtifactRecord[];
 latestFilename:string;
};
export type ValidatedWithdrawal={
 root:string;
 operationDirectory:string;
 metadata:RevisionWithdrawalMetadata;
 marker:any;
 artifacts:LifecycleArtifactRecord[];
};

function exactKeys(value:unknown,keys:string[]) { return !!value&&typeof value==='object'&&JSON.stringify(Object.keys(value).sort())===JSON.stringify([...keys].sort()); }
function within(root:string,candidate:string) { const rel=relative(root,candidate); return rel===''||(!rel.startsWith(`..${sep}`)&&rel!=='..'&&!isAbsolute(rel)); }
function block(code:string):never { throw new Error(code); }
function immutableRelativePath(publicRelativePath:string) { const directoryPrefix=`${artifactConfig.directory}/`; return publicRelativePath.startsWith(directoryPrefix)?`artifacts/${publicRelativePath}`:`artifacts/${publicRelativePath.replace(new RegExp(`^${artifactConfig.sidecarRoot.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')}\\/`),'')}`; }

export function parseManagedRevisionFilename(filename:string):ManagedRevisionIdentity {
 if (basename(filename)!==filename||!MANAGED(filename)) block('INVALID_MANAGED_REVISION_FILENAME');
 const parsed=parseManagedRevision(filename)!;
 const revisionNumber=parsed.ordinal;
 if (!Number.isSafeInteger(revisionNumber)||revisionNumber<1) block('INVALID_MANAGED_REVISION_FILENAME');
 const lineage=parsed.lineage;
 const revision=parsed.revision;
 const sourceFilename=managedRevisionFilename(lineage,revisionNumber-1);
 const sourceRevision=artifactConfig.revisionLabel(revisionNumber-1);
 return {filename,lineage,revision,revisionNumber,sourceFilename,sourceRevision};
}

export function assertWithdrawalOperationId(operationId:string) {
 if (!UUID.test(operationId)||basename(operationId)!==operationId) block('INVALID_WITHDRAWAL_OPERATION_ID');
 return operationId;
}

export function lifecyclePublicRelativePaths(filename:string) {
 parseManagedRevisionFilename(filename);
 return publicRelativePaths(filename);
}

export function withdrawalRootPath(root:string) { return join(resolve(root),artifactConfig.sidecarRoot,'withdrawn'); }
export function withdrawalOperationPath(root:string,operationId:string) { return join(withdrawalRootPath(root),assertWithdrawalOperationId(operationId)); }
export function withdrawalStagingPath(root:string,operationId:string) { return join(withdrawalRootPath(root),`.staging-${assertWithdrawalOperationId(operationId)}`); }
export function restoreStagingPath(root:string,operationId:string) { return join(withdrawalRootPath(root),`.restore-staging-${assertWithdrawalOperationId(operationId)}`); }
export function withdrawalMetadataPath(root:string,operationId:string) { return join(withdrawalOperationPath(root,operationId),'metadata.json'); }
export function withdrawalMarkerPath(root:string,operationId:string) { return join(withdrawalOperationPath(root,operationId),'audit-marker.json'); }

export function normalizeWithdrawalReason(reason:unknown) {
 if (reason===undefined) return 'User requested managed revision withdrawal.';
 if (typeof reason!=='string') block('INVALID_WITHDRAWAL_REASON');
 const normalized=reason.replace(/\s+/g,' ').trim();
 if (!normalized||Buffer.byteLength(normalized)>500) block('INVALID_WITHDRAWAL_REASON');
 return normalized;
}

async function canonicalRoot(projectRoot:string) {
 let root:string;
 try { root=await realpath(resolve(projectRoot)); }
 catch { block('PROJECT_ROOT_UNREADABLE'); }
 const info=await lstat(root!);
 if (!info.isDirectory()||info.isSymbolicLink()) block('PROJECT_ROOT_UNSAFE');
 return root!;
}

async function regularBytes(root:string,path:string,missingCode:string) {
 try {
  const info=await lstat(path);
  if (!info.isFile()||info.isSymbolicLink()||info.nlink!==1) block(`${missingCode}_UNSAFE`);
  const resolved=await realpath(path);
  if (resolved!==path||!within(root,resolved)) block(`${missingCode}_UNSAFE`);
  return await readFile(resolved);
 } catch (error) {
  if (error instanceof Error&&error.message.startsWith(missingCode)) throw error;
  block(missingCode);
 }
}

function parseJson(bytes:Buffer,code:string) { try { return JSON.parse(bytes.toString('utf8')); } catch { block(code); } }
function artifactDigest(artifacts:Array<{publicRelativePath:string;sha256:string}>) {
 const inventory=artifacts.map(({publicRelativePath,sha256})=>({publicRelativePath,sha256})).sort((a,b)=>a.publicRelativePath.localeCompare(b.publicRelativePath));
 return sha256(JSON.stringify(inventory));
}

export type ManagedRevisionCandidate={filename:string;revisionNumber:number};
export type ResolveLatestManagedRevisionOptions={markerOwned?:boolean};
export type LatestManagedRevisionResolution =
 | {status:'empty'}
 | {status:'active';latest:ManagedRevisionCandidate;candidates:ManagedRevisionCandidate[]}
 | {status:'multiple';latest:ManagedRevisionCandidate;candidates:ManagedRevisionCandidate[];code:'MULTIPLE_ACTIVE_REVISIONS'};

/** Pure canonical tie-break (design decision I3/I4): highest revisionNumber; ties broken by ascending filename localeCompare, first element wins. Shared by every "latest managed revision" call site. */
function pickCanonicalLatest(candidates:ManagedRevisionCandidate[]):{tied:ManagedRevisionCandidate[];ordered:ManagedRevisionCandidate[]}|undefined {
 if (!candidates.length) return undefined;
 const ordered=[...candidates].sort((a,b)=>b.revisionNumber-a.revisionNumber||a.filename.localeCompare(b.filename));
 const highest=ordered[0].revisionNumber;
 return {tied:ordered.filter(c=>c.revisionNumber===highest),ordered};
}

/**
 * Single canonical "latest managed revision" resolver (design decision I3/I4), replacing four
 * previously divergent implementations: `ProposalDeliberationOrchestrator.latest()` (returned undefined on
 * tie), `latestManagedFilename` (silently picked one via localeCompare), `readCanonicalManagedRevisionInventory`
 * (always returned at most one, silently suppressing multiplicity), and draft-materialization's
 * `resolvePrimaryDocument` (mtime-based tie-break). Every caller now shares this exact tie-break rule.
 * When two or more managed files tie at the highest revisionNumber, `status` is `'multiple'` -- never
 * silently collapsed -- so a caller can surface MULTIPLE_ACTIVE_REVISIONS instead of guessing.
 */
export async function resolveLatestManagedRevision(projectRoot:string,options:ResolveLatestManagedRevisionOptions={}):Promise<LatestManagedRevisionResolution> {
 const root=await canonicalRoot(projectRoot);
 let entries;
 try { entries=(await readdir(join(root,artifactConfig.directory),{withFileTypes:true})).filter(entry=>entry.isFile()&&MANAGED(entry.name)); }
 catch { block('PROPOSALS_UNREADABLE'); }
 const candidates:ManagedRevisionCandidate[]=[];
 for (const entry of entries!) {
  if (options.markerOwned) {
   let bytes:Buffer;
   try { bytes=await readFile(join(root,artifactConfig.directory,entry.name)); }
   catch { continue; }
   if (!bytes.subarray(0,MARKER.length).equals(MARKER)) continue;
  }
  candidates.push({filename:entry.name,revisionNumber:parseManagedRevisionFilename(entry.name).revisionNumber});
 }
 const picked=pickCanonicalLatest(candidates);
 if (!picked) return {status:'empty'};
 if (picked.tied.length>1) return {status:'multiple',latest:picked.tied[0],candidates:picked.tied,code:'MULTIPLE_ACTIVE_REVISIONS'};
 return {status:'active',latest:picked.tied[0],candidates:picked.ordered};
}

export async function latestManagedFilename(projectRoot:string) {
 const resolution=await resolveLatestManagedRevision(projectRoot);
 return resolution.status==='empty'?undefined:resolution.latest.filename;
}

export async function discoverManagedRevision(input:{projectRoot:string;filename:string}):Promise<ManagedRevisionDiscovery> {
 const identity=parseManagedRevisionFilename(input.filename);
 if (identity.revisionNumber===1) block('BASE_REVISION_WITHDRAWAL_BLOCKED');
 const root=await canonicalRoot(input.projectRoot);
 const publicPaths=lifecyclePublicRelativePaths(identity.filename);
 const documentPath=join(root,publicPaths[0]);
 const statePath=derivedStatePath(root,identity.filename);
 const storedReceiptPath=receiptPath(root,identity.filename);
 const documentBytes=await regularBytes(root,documentPath,'MANAGED_DOCUMENT_MISSING');
 const stateBytes=await regularBytes(root,statePath,'MANAGED_STATE_MISSING');
 const receiptBytes=await regularBytes(root,storedReceiptPath,'MANAGED_RECEIPT_MISSING');
 if (!documentBytes.subarray(0,MARKER.length).equals(MARKER)) block('UNMANAGED_REVISION');
 const documentSha256=sha256(documentBytes);
 const state=parseJson(stateBytes,'MALFORMED_MANAGED_STATE');
 const receipt=parseJson(receiptBytes,'MALFORMED_MANAGED_RECEIPT');
 if (state?.manifest?.status!=='COMMITTED'||!validateStoredState(state,identity.filename,documentSha256,PARSER_VERSION,documentBytes)) block('MANAGED_STATE_IDENTITY_MISMATCH');
 if (state.manifest.revision!==identity.revision) block('MANAGED_STATE_REVISION_MISMATCH');
 if (!receipt||receipt.targetFilename!==identity.filename||receipt.targetRevision!==identity.revision||receipt.documentShaAfter!==documentSha256||receipt.derivedStateStatus!=='COMMITTED') block('MANAGED_RECEIPT_IDENTITY_MISMATCH');
 if (receipt.sourceRevision!==identity.sourceRevision||receipt.sourceFilename!==identity.sourceFilename) block('MANAGED_RECEIPT_SOURCE_MISMATCH');
 const sourceBytes=await regularBytes(root,join(root,artifactConfig.directory,identity.sourceFilename),'SOURCE_REVISION_MISSING');
 if (!sourceBytes.subarray(0,MARKER.length).equals(MARKER)) block('SOURCE_REVISION_UNMANAGED');
 let publicEntries;
 try { publicEntries=await readdir(join(root,artifactConfig.directory),{withFileTypes:true}); }
 catch { block('PROPOSALS_UNREADABLE'); }
 for (const entry of publicEntries) {
  if (!entry.isFile()||!MANAGED(entry.name)||entry.name===identity.filename) continue;
  const later=parseManagedRevisionFilename(entry.name);
  if (later.lineage!==identity.lineage||later.revisionNumber<=identity.revisionNumber) continue;
  if (later.revisionNumber===identity.revisionNumber+1) block('LATER_DEPENDENT_REVISION_EXISTS');
  let laterReceipt:any;
  try { laterReceipt=JSON.parse((await regularBytes(root,receiptPath(root,entry.name),'MALFORMED_LATER_REVISION_RECEIPT')).toString('utf8')); }
  catch { block('MALFORMED_LATER_REVISION_RECEIPT'); }
  if (!laterReceipt||laterReceipt.targetFilename!==entry.name||typeof laterReceipt.sourceRevision!=='string') block('MALFORMED_LATER_REVISION_RECEIPT');
  if (laterReceipt.sourceRevision===identity.revision||laterReceipt.sourceFilename===identity.filename) block('LATER_DEPENDENT_REVISION_EXISTS');
 }
 const artifacts:LifecycleArtifactRecord[]=[
  {publicRelativePath:publicPaths[0],quarantineRelativePath:immutableRelativePath(publicPaths[0]),absolutePath:documentPath,bytes:documentBytes,sha256:documentSha256},
  {publicRelativePath:publicPaths[1],quarantineRelativePath:immutableRelativePath(publicPaths[1]),absolutePath:statePath,bytes:stateBytes,sha256:sha256(stateBytes)},
  {publicRelativePath:publicPaths[2],quarantineRelativePath:immutableRelativePath(publicPaths[2]),absolutePath:storedReceiptPath,bytes:receiptBytes,sha256:sha256(receiptBytes)},
 ];
 return {...identity,root,documentSha256,state,receipt,artifacts,latestFilename:(await latestManagedFilename(root))!};
}

export const validateWithdrawalEligibility=discoverManagedRevision;

export function validateWithdrawalMetadata(value:any,operationId:string) {
 if (!exactKeys(value,METADATA_KEYS)||value.schemaVersion!=='1'||value.operationId!==operationId||!UUID.test(value.operationId)||!MANAGED(value.requestedFilename)||!strictRevisionLabel(value.revision)||!SHA.test(value.documentSha256)||!strictRevisionLabel(value.sourceRevision)||!MANAGED(value.sourceFilename)||typeof value.reason!=='string'||!value.reason||Buffer.byteLength(value.reason)>500||!MANAGED(value.preWithdrawalLatestFilename)||!Number.isFinite(Date.parse(value.operationTimestamp))) block('INVALID_WITHDRAWAL_METADATA');
 const identity=parseManagedRevisionFilename(value.requestedFilename);
 if (identity.revision!==value.revision||identity.sourceRevision!==value.sourceRevision||identity.sourceFilename!==value.sourceFilename||identity.revisionNumber===1) block('INVALID_WITHDRAWAL_METADATA_IDENTITY');
 if (!Array.isArray(value.artifacts)||value.artifacts.length!==3) block('INVALID_WITHDRAWAL_INVENTORY');
 const expected:string[]=[...lifecyclePublicRelativePaths(value.requestedFilename)];
 const seen=new Set<string>();
 for (const artifact of value.artifacts) {
  if (!exactKeys(artifact,['publicRelativePath','quarantineRelativePath','sha256'])||!expected.includes(artifact.publicRelativePath)||artifact.quarantineRelativePath!==immutableRelativePath(artifact.publicRelativePath)||!SHA.test(artifact.sha256)||seen.has(artifact.publicRelativePath)) block('INVALID_WITHDRAWAL_INVENTORY');
  seen.add(artifact.publicRelativePath);
 }
 if (seen.size!==3||artifactDigest(value.artifacts)!==value.inventoryDigest) block('INVALID_WITHDRAWAL_INVENTORY_DIGEST');
 return value as RevisionWithdrawalMetadata;
}

export async function findWithdrawal(input:{projectRoot:string;operationId?:string;filename?:string}):Promise<ValidatedWithdrawal> {
 const root=await canonicalRoot(input.projectRoot);
 if (!input.operationId&&!input.filename) block('WITHDRAWAL_IDENTITY_REQUIRED');
 if (input.filename) parseManagedRevisionFilename(input.filename);
 let operationIds:string[];
 if (input.operationId) operationIds=[assertWithdrawalOperationId(input.operationId)];
 else {
  let entries;
  try { entries=await readdir(withdrawalRootPath(root),{withFileTypes:true}); }
  catch { block('WITHDRAWAL_NOT_FOUND'); }
  operationIds=entries.filter(entry=>entry.isDirectory()&&UUID.test(entry.name)).map(entry=>entry.name);
 }
 const matches:ValidatedWithdrawal[]=[];
 for (const operationId of operationIds) {
  const operationDirectory=withdrawalOperationPath(root,operationId);
  try {
   const info=await lstat(operationDirectory);
   if (!info.isDirectory()||info.isSymbolicLink()||(await realpath(operationDirectory))!==operationDirectory) continue;
   const metadata=validateWithdrawalMetadata(parseJson(await regularBytes(root,join(operationDirectory,'metadata.json'),'WITHDRAWAL_METADATA_MISSING'),'MALFORMED_WITHDRAWAL_METADATA'),operationId);
   if (input.filename&&metadata.requestedFilename!==input.filename) continue;
   const marker=parseJson(await regularBytes(root,join(operationDirectory,'audit-marker.json'),'WITHDRAWAL_MARKER_MISSING'),'MALFORMED_WITHDRAWAL_MARKER');
   if (marker.state!=='COMMITTED'||marker.operationType!=='WITHDRAW_REVISION'||marker.operationId!==operationId||marker.auditStatus!=='PASS'||marker.selfAuditStatus!=='PASS'||marker.inventoryDigest!==metadata.inventoryDigest) continue;
   const artifacts:LifecycleArtifactRecord[]=[];
   for (const artifact of metadata.artifacts) {
    const absolutePath=join(operationDirectory,artifact.quarantineRelativePath);
    const bytes=await regularBytes(root,absolutePath,'WITHDRAWAL_ARTIFACT_MISSING');
    if (sha256(bytes)!==artifact.sha256) block('WITHDRAWAL_ARTIFACT_SHA_MISMATCH');
    artifacts.push({...artifact,absolutePath,bytes});
   }
   const document=artifacts.find(artifact=>artifact.publicRelativePath.startsWith(`${artifactConfig.directory}/`))!;
   const stateArtifact=artifacts.find(artifact=>artifact.publicRelativePath.includes('/state/'))!;
   const receiptArtifact=artifacts.find(artifact=>artifact.publicRelativePath.includes('/receipts/'))!;
   if (!document.bytes.subarray(0,MARKER.length).equals(MARKER)||sha256(document.bytes)!==metadata.documentSha256) block('WITHDRAWAL_DOCUMENT_IDENTITY_MISMATCH');
   const state=parseJson(stateArtifact.bytes,'MALFORMED_WITHDRAWAL_STATE');
   const receipt=parseJson(receiptArtifact.bytes,'MALFORMED_WITHDRAWAL_RECEIPT');
   if (state?.manifest?.status!=='COMMITTED'||state.manifest.revision!==metadata.revision||!validateStoredState(state,metadata.requestedFilename,metadata.documentSha256,PARSER_VERSION,document.bytes)) block('WITHDRAWAL_STATE_IDENTITY_MISMATCH');
   if (receipt?.targetFilename!==metadata.requestedFilename||receipt.targetRevision!==metadata.revision||receipt.documentShaAfter!==metadata.documentSha256||receipt.sourceRevision!==metadata.sourceRevision||receipt.sourceFilename!==metadata.sourceFilename||receipt.derivedStateStatus!=='COMMITTED') block('WITHDRAWAL_RECEIPT_IDENTITY_MISMATCH');
   matches.push({root,operationDirectory,metadata,marker,artifacts});
  } catch (error) {
   if (input.operationId) throw error;
  }
 }
 if (matches.length===0) block('WITHDRAWAL_NOT_FOUND');
 if (matches.length!==1) block('WITHDRAWAL_LOOKUP_AMBIGUOUS');
 return matches[0];
}

export function lifecycleInventoryDigest(artifacts:Array<{publicRelativePath:string;sha256:string}>) { return artifactDigest(artifacts); }

export type LifecycleV1ReadInventory =
 | { status:'valid'; lifecycleState:'EMPTY'|'BASE_REGISTERED'|'ACTIVE'|'WITHDRAWN_ONLY'; baseDocument?:BaseDocument; activeRevision?:LifecycleRevision; revisions:Array<LifecycleRevision&{state:'ACTIVE'|'SUPERSEDED'|'WITHDRAWN'}>; withdrawals:WithdrawalRecord[]; auditEvidence:string[] }
 | { status:'unregistered'; code:'LIFECYCLE_V1_UNREGISTERED'; auditEvidence:string[] }
 | { status:'inconsistent'; code:string; auditEvidence:string[] };

/** Reads only explicit lifecycle-v1 authority; it never consults proposal filenames or legacy withdrawals. */
export async function readLifecycleV1Inventory(input:{projectRoot:string;workspaceId:string}):Promise<LifecycleV1ReadInventory> {
 try {
  const service=new LifecycleService(input.projectRoot);
  if(!await service.hasLifecycleAuthority(input.workspaceId)) return {status:'unregistered',code:'LIFECYCLE_V1_UNREGISTERED',auditEvidence:['lifecycle-v1:authority-unregistered']};
  const inventory=await service.rebuildLifecycleInventory(input.workspaceId);
  if(inventory.lifecycleState==='INCONSISTENT') return {status:'inconsistent',code:'LIFECYCLE_INVENTORY_INCONSISTENT',auditEvidence:['lifecycle-v1:rebuild-inconsistent']};
  return {status:'valid',lifecycleState:inventory.lifecycleState,baseDocument:inventory.base,activeRevision:inventory.revisions.find(revision=>revision.revisionId===inventory.activeRevisionId),revisions:inventory.revisions,withdrawals:inventory.withdrawals,auditEvidence:['lifecycle-v1:rebuild-read-only']};
 } catch(error) { return {status:'inconsistent',code:error instanceof Error?error.message:'LIFECYCLE_INVENTORY_INCONSISTENT',auditEvidence:['lifecycle-v1:rebuild-blocked']}; }
}

/** Adapts explicit lifecycle-v1 records to the existing read-only project-entry port. */
export function createLifecycleV1RevisionInventoryPort(input:{projectRoot:string;workspaceId:string}) {
 return { read: async () => {
  const inventory=await readLifecycleV1Inventory(input);
  if(inventory.status==='inconsistent') return {status:'inconsistent' as const,code:inventory.code,auditEvidence:inventory.auditEvidence};
  if(inventory.status==='unregistered') return {status:'valid' as const,activeRevisions:[],withdrawnRevisions:[],lifecycleState:'EMPTY' as const,auditEvidence:inventory.auditEvidence};
  const evidence=(revision:LifecycleRevision&{state:'ACTIVE'|'SUPERSEDED'|'WITHDRAWN'})=>({filename:revision.locator??'',revision:revision.revisionId,revisionId:revision.revisionId,documentSha256:revision.contentHash,baseDocumentId:revision.baseDocumentId,lineage:revision.lineage});
  return {status:'valid' as const,activeRevisions:inventory.activeRevision?[evidence(inventory.activeRevision as LifecycleRevision&{state:'ACTIVE'|'SUPERSEDED'|'WITHDRAWN'})]:[],withdrawnRevisions:inventory.revisions.filter(revision=>revision.state==='WITHDRAWN').map(evidence),baseDocument:inventory.baseDocument?{baseDocumentId:inventory.baseDocument.baseDocumentId,contentHash:inventory.baseDocument.contentHash}:undefined,lifecycleState:inventory.lifecycleState,auditEvidence:inventory.auditEvidence};
 }};
}

/** Read-only canonical managed-revision inventory for scientific entry admission. */
export type CanonicalManagedRevisionInventory =
 | { status:'valid'; activeRevisions:Array<{filename:string;revision:string;documentSha256:string}>; withdrawnRevisions:Array<{filename:string;revision:string;documentSha256:string}>; auditEvidence:string[] }
 | { status:'inconsistent'; code:string; auditEvidence:string[] };

export async function readCanonicalManagedRevisionInventory(projectRoot:string):Promise<CanonicalManagedRevisionInventory> {
 try {
  const root=await canonicalRoot(projectRoot);
  const entries=await readdir(join(root,artifactConfig.directory),{withFileTypes:true});
  const revisions:Array<{filename:string;revision:string;documentSha256:string;revisionNumber:number}>=[];
  for(const entry of entries) {
   if(!entry.isFile()||!MANAGED(entry.name)) continue;
   const identity=parseManagedRevisionFilename(entry.name);
   const document=await regularBytes(root,join(root,artifactConfig.directory,entry.name),'MANAGED_DOCUMENT_MISSING');
   if(!document.subarray(0,MARKER.length).equals(MARKER)) block('UNMANAGED_REVISION');
   const documentSha256=sha256(document);
   const state=parseJson(await regularBytes(root,derivedStatePath(root,entry.name),'MANAGED_STATE_MISSING'),'MALFORMED_MANAGED_STATE');
   if(state?.manifest?.status!=='COMMITTED'||!validateStoredState(state,entry.name,documentSha256,PARSER_VERSION,document)) block('MANAGED_STATE_IDENTITY_MISMATCH');
   revisions.push({filename:entry.name,revision:identity.revision,documentSha256,revisionNumber:identity.revisionNumber});
  }
  const picked=pickCanonicalLatest(revisions);
  const tiedFilenames=new Set((picked?.tied??[]).map(candidate=>candidate.filename));
  const activeRevisions=revisions.filter(revision=>tiedFilenames.has(revision.filename)).map(({filename,revision,documentSha256})=>({filename,revision,documentSha256}));
  return {status:'valid',activeRevisions,withdrawnRevisions:[],auditEvidence:['revision-inventory:canonical-read-only',...(picked&&picked.tied.length>1?['revision-inventory:multiple-active-revisions']:[])]};
 } catch(error) {
  return {status:'inconsistent',code:error instanceof Error?error.message:'REVISION_INVENTORY_UNAVAILABLE',auditEvidence:['revision-inventory:canonical-read-only-blocked']};
 }
}
