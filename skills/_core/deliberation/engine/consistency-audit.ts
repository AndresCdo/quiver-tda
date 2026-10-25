import { lstat, readdir, readFile, realpath } from 'node:fs/promises';
import { isAbsolute, join, relative, sep } from 'node:path';
import { derivedStatePath, receiptPath, validateStoredState } from './derived-state-store.js';
import { validateWithdrawalMetadata } from './revision-lifecycle-store.js';
import { withMutationLock } from './mutation-lock.js';
import { PARSER_VERSION, PENDING_AUDIT_LEASE_MS, sha256, type PendingAuditArtifact, type PendingAuditContext, type RevisionLifecycleLockOwner } from './types.js';
import { artifact as artifactConfig, documentPath, receiptPath as managedReceiptPath, statePath, strictManagedRevision, withdrawnMarkerPath } from './artifact-naming.js';

const UUID=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const MANAGED=strictManagedRevision;
const SHA=/^[0-9a-f]{64}$/;
const activePendingAudits=new Map<string,{root:string;context:PendingAuditContext;owner:RevisionLifecycleLockOwner}>();
const activeLifecycleLockOwners=new WeakMap<RevisionLifecycleLockOwner,{root:string;operationId:string;filename:string}>();

function result(status:string, id:string, category:string, evidence:unknown, details:string) {
  return { id, status, category, evidence, details };
}

function operationKey(root:string,operationId:string) { return `${root}\0${operationId}`; }
function lifecycleMutationLockKey(root:string,filename:string) { return `revision-lifecycle\0${root}\0${filename}`; }
function isWithin(root:string,path:string) { const value=relative(root,path); return value===''||(!value.startsWith(`..${sep}`)&&value!=='..'&&!isAbsolute(value)); }
function expectedMarkerPath(operationId:string) { return withdrawnMarkerPath(operationId); }
function hasExactKeys(value:unknown,keys:string[]) { return !!value&&typeof value==='object'&&JSON.stringify(Object.keys(value).sort())===JSON.stringify([...keys].sort()); }

function declaredLifecycleFilename(context:PendingAuditContext) {
  const directoryPrefix=`${artifactConfig.directory}/`;
  const proposal=context.temporarilyMovedArtifacts.find(entry=>entry.publicRelativePath.startsWith(directoryPrefix));
  const filename=proposal?.publicRelativePath.slice(directoryPrefix.length);
  return filename&&MANAGED(filename)?filename:undefined;
}

export async function withRevisionLifecycleMutationLock<T>(input:{projectRoot:string;operationId:string;filename:string},run:(owner:RevisionLifecycleLockOwner)=>Promise<T>):Promise<T> {
  const root=await realpath(input.projectRoot);
  if (!UUID.test(input.operationId)||!MANAGED(input.filename)) throw new Error('INVALID_REVISION_LIFECYCLE_LOCK_IDENTITY');
  return withMutationLock(lifecycleMutationLockKey(root,input.filename),async()=>{
    const owner=Object.freeze({operationId:input.operationId,filename:input.filename});
    activeLifecycleLockOwners.set(owner,{root,operationId:input.operationId,filename:input.filename});
    try { return await run(owner); }
    finally { activeLifecycleLockOwners.delete(owner); }
  });
}

export function pendingAuditInventoryDigest(artifacts:PendingAuditArtifact[]) {
  const inventory=artifacts.map(({publicRelativePath,sha256})=>({publicRelativePath,sha256})).sort((a,b)=>a.publicRelativePath.localeCompare(b.publicRelativePath));
  return sha256(JSON.stringify(inventory));
}

export async function withActivePendingAuditOperation<T>(input:{projectRoot:string;auditContext:PendingAuditContext;lifecycleLockOwner:RevisionLifecycleLockOwner},run:()=>Promise<T>):Promise<T> {
  const root=await realpath(input.projectRoot);
  const filename=declaredLifecycleFilename(input.auditContext);
  const owner=activeLifecycleLockOwners.get(input.lifecycleLockOwner);
  if (!filename||!owner||owner.root!==root||owner.operationId!==input.auditContext.operationId||owner.filename!==filename) throw new Error('PENDING_AUDIT_REQUIRES_MATCHING_LIFECYCLE_LOCK_OWNER');
  const key=operationKey(root,input.auditContext.operationId);
  if (activePendingAudits.has(key)) throw new Error('PENDING_AUDIT_OPERATION_ALREADY_ACTIVE');
  activePendingAudits.set(key,{root,context:input.auditContext,owner:input.lifecycleLockOwner});
  try { return await run(); }
  finally { if (activePendingAudits.get(key)?.context===input.auditContext) activePendingAudits.delete(key); }
}

function activeOperation(root:string,context:PendingAuditContext) {
  const active=activePendingAudits.get(operationKey(root,context.operationId));
  if (!active||active.root!==root||active.context!==context) return false;
  const owner=activeLifecycleLockOwners.get(active.owner);
  return owner?.root===root&&owner.operationId===context.operationId&&owner.filename===declaredLifecycleFilename(context);
}

export async function hasActivePendingAuditLifecycleOperation(input:{projectRoot:string;auditContext:PendingAuditContext}) {
  try { return activeOperation(await realpath(input.projectRoot),input.auditContext); }
  catch { return false; }
}

function validateArtifactList(artifacts:unknown,operationType:unknown,failures:string[],prefix:string):artifacts is PendingAuditArtifact[] {
  if (!Array.isArray(artifacts)||artifacts.length!==3) { failures.push(`${prefix}_ARTIFACT_COUNT`); return false; }
  const expectedLocation=operationType==='WITHDRAW_REVISION'?'quarantine-public-backup':operationType==='RESTORE_WITHDRAWN_REVISION'?'public':undefined;
  const paths=new Set<string>();
  let filename:string|undefined;
  let valid=Boolean(expectedLocation);
  for (const artifact of artifacts) {
    if (!hasExactKeys(artifact,['publicRelativePath','sha256','expectedLocation'])||typeof artifact.publicRelativePath!=='string'||typeof artifact.sha256!=='string'||artifact.expectedLocation!==expectedLocation||!SHA.test(artifact.sha256)) { valid=false; continue; }
    if (paths.has(artifact.publicRelativePath)) valid=false;
    paths.add(artifact.publicRelativePath);
    const escapedDirectory=artifactConfig.directory.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
    const escapedSidecarRoot=artifactConfig.sidecarRoot.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
    const match=artifact.publicRelativePath.match(new RegExp(`^(?:${escapedDirectory}\\/(.+)|${escapedSidecarRoot}\\/(?:state|receipts)\\/(.+)\\.json)$`));
    const candidate=match?.[1]??match?.[2];
    if (!candidate||!MANAGED(candidate)||filename&&candidate!==filename) valid=false;
    else filename=candidate;
  }
  if (filename) {
    const expected=new Set([documentPath(filename),statePath(filename),managedReceiptPath(filename)]);
    if (paths.size!==expected.size||[...expected].some(path=>!paths.has(path))) valid=false;
  }
  if (!valid) failures.push(`${prefix}_INVALID_ARTIFACT_DECLARATION`);
  return valid;
}

function immutableRelativePath(publicRelativePath:string) {
  const directoryPrefix=`${artifactConfig.directory}/`;
  if (publicRelativePath.startsWith(directoryPrefix)) return `artifacts/${publicRelativePath}`;
  const sidecarPrefix=`${artifactConfig.sidecarRoot}/`;
  return `artifacts/${publicRelativePath.startsWith(sidecarPrefix)?publicRelativePath.slice(sidecarPrefix.length):publicRelativePath}`;
}

async function readRegularWithin(root:string,path:string,failures:string[],code:string) {
  try {
    const info=await lstat(path);
    if (!info.isFile()||info.isSymbolicLink()) throw new Error('not a regular file');
    const resolved=await realpath(path);
    if (!isWithin(root,resolved)) throw new Error('outside project root');
    return await readFile(resolved);
  } catch { failures.push(code); return undefined; }
}

async function resolveDirectoryWithin(root:string,directory:string) {
  const info=await lstat(directory);
  if (!info.isDirectory()||info.isSymbolicLink()) throw new Error('not a regular directory');
  const resolved=await realpath(directory);
  if (!isWithin(root,resolved)) throw new Error('outside project root');
  return resolved;
}

async function collectFiles(root:string,directory:string,failures:string[],code:string):Promise<string[]> {
  const files:string[]=[];
  let base:string;
  try { base=await resolveDirectoryWithin(root,directory); }
  catch { failures.push(code); return files; }
  async function visit(current:string) {
    let entries;
    try { entries=await readdir(current,{withFileTypes:true}); }
    catch { failures.push(code); return; }
    for (const entry of entries) {
      const path=join(current,entry.name);
      if (entry.isSymbolicLink()) { failures.push(`${code}_SYMLINK:${relative(base,path)}`); continue; }
      if (entry.isDirectory()) await visit(path);
      else if (entry.isFile()) files.push(relative(base,path).split(sep).join('/'));
      else failures.push(`${code}_UNSUPPORTED:${relative(base,path)}`);
    }
  }
  await visit(base);
  return files.sort();
}

async function verifyExactTree(root:string,directory:string,expected:string[],failures:string[],prefix:string) {
  const found=await collectFiles(root,directory,failures,`${prefix}_TREE_UNREADABLE`);
  for (const path of found) if (!expected.includes(path)) failures.push(`${prefix}_UNDECLARED_ARTIFACT:${path}`);
  for (const path of expected) if (!found.includes(path)) failures.push(`${prefix}_MISSING_ARTIFACT:${path}`);
}

async function verifyPlacement(root:string,operationDirectory:string,artifacts:PendingAuditArtifact[],failures:string[],prefix:string) {
  const immutableExpected=artifacts.map(artifact=>immutableRelativePath(artifact.publicRelativePath).slice('artifacts/'.length));
  await verifyExactTree(root,join(operationDirectory,'artifacts'),immutableExpected,failures,`${prefix}_IMMUTABLE`);
  const backupExpected=artifacts.map(artifact=>artifact.publicRelativePath);
  const withdrawal=artifacts[0]?.expectedLocation==='quarantine-public-backup';
  if (withdrawal) await verifyExactTree(root,join(operationDirectory,'public-backup'),backupExpected,failures,`${prefix}_PUBLIC_BACKUP`);
  else {
    try { await lstat(join(operationDirectory,'public-backup')); await verifyExactTree(root,join(operationDirectory,'public-backup'),backupExpected,failures,`${prefix}_RETAINED_PUBLIC_BACKUP`); }
    catch {}
  }
  for (const artifact of artifacts) {
    const immutable=join(operationDirectory,immutableRelativePath(artifact.publicRelativePath));
    const immutableBytes=await readRegularWithin(root,immutable,failures,`${prefix}_MISSING_IMMUTABLE:${artifact.publicRelativePath}`);
    if (immutableBytes&&sha256(immutableBytes)!==artifact.sha256) failures.push(`${prefix}_SHA_MISMATCH:${artifact.publicRelativePath}`);
    const observed=artifact.expectedLocation==='public'?join(root,artifact.publicRelativePath):join(operationDirectory,'public-backup',artifact.publicRelativePath);
    const observedBytes=await readRegularWithin(root,observed,failures,`${prefix}_MISSING_EXPECTED_LOCATION:${artifact.publicRelativePath}`);
    if (observedBytes&&sha256(observedBytes)!==artifact.sha256) failures.push(`${prefix}_SHA_MISMATCH:${artifact.publicRelativePath}`);
    if (withdrawal) {
      try { await lstat(join(root,artifact.publicRelativePath)); failures.push(`${prefix}_PUBLIC_ARTIFACT_STILL_PRESENT:${artifact.publicRelativePath}`); }
      catch {}
    }
  }
}

function validPhase(operationType:unknown,phase:unknown) {
  return operationType==='WITHDRAW_REVISION'&&phase==='WITHDRAW_PUBLIC_ARTIFACTS_MOVED'||operationType==='RESTORE_WITHDRAWN_REVISION'&&phase==='RESTORE_PUBLIC_ARTIFACTS_MOVED';
}

async function validateOperationMetadata(root:string,operationDirectory:string,marker:any,failures:string[]) {
  let metadata:any;
  try {
    const bytes=await readRegularWithin(root,join(operationDirectory,'metadata.json'),failures,`MISSING_WITHDRAWAL_METADATA:${marker.operationId??'unknown'}`);
    if (!bytes) return;
    metadata=validateWithdrawalMetadata(JSON.parse(bytes.toString('utf8')),marker.operationId);
  } catch { failures.push(`INVALID_WITHDRAWAL_METADATA:${marker.operationId??'unknown'}`); return; }
  if (metadata.inventoryDigest!==marker.inventoryDigest) failures.push(`WITHDRAWAL_METADATA_DIGEST_MISMATCH:${marker.operationId}`);
  const expected=metadata.artifacts.map((artifact:any)=>({publicRelativePath:artifact.publicRelativePath,sha256:artifact.sha256,expectedLocation:marker.operationType==='WITHDRAW_REVISION'?'quarantine-public-backup':'public'}));
  if (JSON.stringify(expected)!==JSON.stringify(marker.temporarilyMovedArtifacts)) failures.push(`WITHDRAWAL_METADATA_ARTIFACT_MISMATCH:${marker.operationId}`);
}

async function validatePendingMarker(root:string,operationDirectory:string,marker:any,context:PendingAuditContext|undefined,failures:string[]) {
  const prefix='PENDING_AUDIT';
  if (!context||context.operationId!==marker.operationId) { failures.push(`${prefix}_WITHOUT_ACTIVE_OPERATION:${marker.operationId??'unknown'}`); return; }
  if (!activeOperation(root,context)) failures.push(`${prefix}_INACTIVE_OPERATION:${context.operationId}`);
  if (!hasExactKeys(context,['operationType','operationId','pendingAudit','phase','temporarilyMovedArtifacts','expectedMarker'])||!hasExactKeys(context.expectedMarker,['relativePath','state','inventoryDigest','expiresAt'])||context.pendingAudit!==true||!UUID.test(context.operationId)||context.operationType!==marker.operationType||context.phase!==marker.phase||!validPhase(context.operationType,context.phase)) failures.push(`${prefix}_CONTEXT_MISMATCH:${context.operationId}`);
  if (context.expectedMarker?.relativePath!==expectedMarkerPath(context.operationId)||context.expectedMarker?.state!=='PENDING_AUDIT'||context.expectedMarker?.inventoryDigest!==marker.inventoryDigest||context.expectedMarker?.expiresAt!==marker.expiresAt) failures.push(`${prefix}_MARKER_MISMATCH:${context.operationId}`);
  if (JSON.stringify(context.temporarilyMovedArtifacts)!==JSON.stringify(marker.temporarilyMovedArtifacts)) failures.push(`${prefix}_MARKER_ARTIFACT_MISMATCH:${context.operationId}`);
  const artifactsValid=validateArtifactList(context.temporarilyMovedArtifacts,context.operationType,failures,prefix);
  if (artifactsValid&&pendingAuditInventoryDigest(context.temporarilyMovedArtifacts)!==context.expectedMarker.inventoryDigest) failures.push(`${prefix}_INVENTORY_DIGEST_MISMATCH:${context.operationId}`);
  const created=Date.parse(marker.createdAt),expires=Date.parse(marker.expiresAt),now=Date.now();
  if (!Number.isFinite(created)||!Number.isFinite(expires)||expires<created||expires-created>PENDING_AUDIT_LEASE_MS||now<created||now>expires) failures.push(`${prefix}_EXPIRED:${context.operationId}`);
  if (artifactsValid) await verifyPlacement(root,operationDirectory,context.temporarilyMovedArtifacts,failures,prefix);
}

async function validateCommittedMarker(root:string,operationDirectory:string,marker:any,failures:string[]) {
  const prefix='COMMITTED_AUDIT';
  if (!UUID.test(marker.operationId??'')||!validPhase(marker.operationType,marker.phase)||marker.auditStatus!=='PASS'||marker.selfAuditStatus!=='PASS') failures.push(`${prefix}_INVALID_MARKER:${marker.operationId??'unknown'}`);
  const artifactsValid=validateArtifactList(marker.temporarilyMovedArtifacts,marker.operationType,failures,prefix);
  if (artifactsValid&&pendingAuditInventoryDigest(marker.temporarilyMovedArtifacts)!==marker.inventoryDigest) failures.push(`${prefix}_INVENTORY_DIGEST_MISMATCH:${marker.operationId}`);
  if (artifactsValid) await verifyPlacement(root,operationDirectory,marker.temporarilyMovedArtifacts,failures,prefix);
}

async function auditWithdrawals(root:string,context:PendingAuditContext|undefined,failures:string[]) {
  let withdrawn:string;
  let entries;
  try {
    withdrawn=await resolveDirectoryWithin(root,join(root,artifactConfig.sidecarRoot,'withdrawn'));
    entries=await readdir(withdrawn,{withFileTypes:true});
  } catch {
    if (context) failures.push(`PENDING_AUDIT_OPERATION_NOT_FOUND:${context.operationId}`);
    else {
      try { await lstat(join(root,artifactConfig.sidecarRoot,'withdrawn')); failures.push('WITHDRAWAL_ROOT_UNSAFE'); }
      catch {}
    }
    return;
  }
  let contextSeen=false;
  for (const entry of entries) {
    if (entry.name.startsWith('.staging-')||entry.name.startsWith('.restore-staging-')) { failures.push(`ORPHAN_WITHDRAWAL_STAGING:${entry.name}`); continue; }
    if (!entry.isDirectory()||!UUID.test(entry.name)) { failures.push(`ORPHAN_WITHDRAWAL_ENTRY:${entry.name}`); continue; }
    const operationDirectory=join(withdrawn,entry.name);
    const markerBytes=await readRegularWithin(root,join(operationDirectory,'audit-marker.json'),failures,`MISSING_AUDIT_MARKER:${entry.name}`);
    if (!markerBytes) continue;
    let marker:any;
    try { marker=JSON.parse(markerBytes.toString('utf8')); }
    catch { failures.push(`MALFORMED_AUDIT_MARKER:${entry.name}`); continue; }
    if (marker.operationId!==entry.name) { failures.push(`AUDIT_MARKER_OPERATION_MISMATCH:${entry.name}`); continue; }
    if (context?.operationId===entry.name) contextSeen=true;
    await validateOperationMetadata(root,operationDirectory,marker,failures);
    if (marker.state==='PENDING_AUDIT') await validatePendingMarker(root,operationDirectory,marker,context,failures);
    else if (marker.state==='COMMITTED') {
      if (context?.operationId===entry.name) failures.push(`PENDING_AUDIT_MARKER_MISMATCH:${entry.name}`);
      await validateCommittedMarker(root,operationDirectory,marker,failures);
    }
    else failures.push(`INVALID_AUDIT_MARKER_STATE:${entry.name}`);
  }
  if (context&&!contextSeen) failures.push(`PENDING_AUDIT_OPERATION_NOT_FOUND:${context.operationId}`);
}

export async function runConsistencyAudit(input:{projectRoot:string;auditContext?:PendingAuditContext}) {
  const checks:any[]=[];
  const failures:string[]=[];
  const warnings:string[]=[];
  let root:string;
  try { root=await realpath(input.projectRoot); }
  catch { root=input.projectRoot; failures.push('PROJECT_ROOT_UNREADABLE'); }
  let revisions:string[]=[];
  try {
    revisions=(await readdir(join(root,artifactConfig.directory))).filter((name:string)=>MANAGED(name));
  } catch {
    failures.push('PROPOSALS_UNREADABLE');
  }
  for (const filename of revisions) {
    const bytes=await readFile(join(root,artifactConfig.directory,filename));
    const hash=sha256(bytes);
    let stored:any;
    let receipt:any;
    try { stored=JSON.parse(await readFile(derivedStatePath(root,filename),'utf8')); }
    catch { failures.push(`MISSING_MANIFEST:${filename}`); }
    if (stored) {
      const committed=stored.manifest?.status==='COMMITTED';
      const valid=validateStoredState(stored,filename,hash,PARSER_VERSION,bytes);
      if (committed&&!valid) failures.push(`INVALID_COMMITTED_MANIFEST:${filename}`);
      if (stored.manifest?.documentSha256&&stored.manifest.documentSha256!==hash) failures.push(`MANIFEST_SHA_MISMATCH:${filename}`);
    }
    try { receipt=JSON.parse(await readFile(receiptPath(root,filename),'utf8')); }
    catch { if (!filename.endsWith(`-${artifactConfig.revisionLabel(1)}.md`)) failures.push(`MISSING_RECEIPT:${filename}`); }
    if (receipt) {
      if (receipt.documentShaAfter!==hash) failures.push(`RECEIPT_SHA_MISMATCH:${filename}`);
      if (receipt.sourceRevision&&receipt.sourceRevision!==artifactConfig.revisionLabel(1)&&!revisions.some((name:string)=>name.endsWith(`-${receipt.sourceRevision}.md`))) failures.push(`MISSING_SOURCE_REVISION:${filename}`);
    }
    if (stored?.manifest?.status==='COMMITTED'&&!receipt) failures.push(`COMMITTED_WITHOUT_RECEIPT:${filename}`);
  }
  for (const directory of ['state','receipts']) {
    const path=join(root,artifactConfig.sidecarRoot,directory);
    try {
      const entries=await readdir(path);
      for (const entry of entries) if (entry.endsWith('.json')&&!revisions.includes(entry.slice(0,-5))) failures.push(`ORPHAN_${directory.toUpperCase()}:${entry}`);
      for (const entry of entries) if (entry.endsWith('.tmp')) warnings.push(`ABANDONED_TEMP:${entry}`);
    } catch {}
  }
  await auditWithdrawals(root,input.auditContext,failures);
  const status=failures.length?'FAIL':warnings.length?'WARN':'PASS';
  checks.push(result(status,'revision-manifest-receipt','persistence',{revisions:revisions.length,failures,warnings},failures.concat(warnings).join(', ')));
  return {status,checks,failures,warnings,summary:{passed:status==='PASS'?1:0,warned:status==='WARN'?1:0,failed:status==='FAIL'?1:0}};
}
