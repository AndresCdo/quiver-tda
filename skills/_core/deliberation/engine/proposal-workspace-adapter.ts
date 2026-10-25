import { randomUUID } from 'node:crypto';
import { nextSuccessorTarget, type DocumentOperationGuard, type DocumentOperationGuardInput, type ProposalWorkspaceInput } from './proposal-workspace.js';
import { sha256, type CleanupLevel, type CompiledPatch, type EffectiveOperationProfile, type Intent } from './types.js';
import type { DocumentReviewApproval } from './document-reviewer-gate.js';
import { artifact, managedRevisionFilename, parseManagedRevision, strictManagedRevision, strictRevisionLabel, type ManagedRevisionName } from './artifact-naming.js';

type WorkspaceResult = { details: Record<string, unknown>; content: Array<{ type: string; text: string }> };
type Workspace = { execute(id: string, input: ProposalWorkspaceInput, signal?: AbortSignal): Promise<WorkspaceResult> };
/** The intents that can publish a successor. Narrower than `Intent` because the value is
 *  forwarded verbatim as the guard's `operation`, whose runtime typebox schema in
 *  `proposal-workspace.ts` accepts exactly these six and rejects the rest. */
export type PublishableIntent = NonNullable<DocumentOperationGuardInput['operation']>;
export type PublishSuccessorInput = { intent: PublishableIntent; cleanupLevel: CleanupLevel; effectiveOperationProfile: EffectiveOperationProfile; sourceFilename: string; sourceSha256: string; patches: CompiledPatch[]; modelCalls: number; plannerCalls: number; roleAuthorizations: number; validationResults: Record<string, boolean>; operationId?: string };
export type PublishedSuccessor = { operationId: string; sourceFilename: string; sourceSha256: string; targetFilename: string; targetRevision: string; publishedSha256: string; publishedBytes: Buffer; patchCount: number; workspaceEvidence: Record<string, unknown>; guardEvidence: Record<string, unknown> };
export type ExactApprovedCandidate = { filename: string; revision: string; bytes: Buffer; digest: string };
export type PublishInitialInput = { candidate: ExactApprovedCandidate; approval: DocumentReviewApproval; operationId?: string };
export type PublishedInitial = { operationId: string; targetFilename: ManagedRevisionName; targetRevision: string; publishedSha256: string; publishedBytes: Buffer; candidateDigest: string; workspaceEvidence: Record<string, unknown>; guardEvidence: Record<string, unknown> };
export type PublishApprovedSuccessorInput = PublishSuccessorInput & { candidate: ExactApprovedCandidate; approval: DocumentReviewApproval };

function requireAllowed(receipt: any, step: string) { if (receipt?.decision !== 'allowed') throw new Error(`PROPOSAL_ADAPTER_${step}_${receipt?.reason?.code ?? 'DENIED'}`); return receipt; }
function managedBytes(result: WorkspaceResult): Buffer { const bytes = result.details.managedBytes; if (Buffer.isBuffer(bytes)) return bytes; if (typeof bytes === 'string') return Buffer.from(bytes, 'utf8'); throw new Error('MANAGED_READ_BYTES_UNAVAILABLE'); }
function verifyApproval(candidate: ExactApprovedCandidate, approval: DocumentReviewApproval) {
 if (approval.decision !== 'APPROVE' || approval.candidateDigest !== candidate.digest || sha256(candidate.bytes) !== candidate.digest) throw new Error('DOCUMENT_REVIEW_APPROVAL_INVALID');
}

export class ProposalWorkspaceAdapter {
 constructor(private readonly projectRoot: string, private readonly guard: DocumentOperationGuard, private readonly workspace: Workspace, private readonly operationIdFactory: () => string = () => `deliberation-`) {}

 /** Publishes only an exact Document Reviewer-approved first-revision candidate through INITIAL_CREATE. */
 async publishInitial(input: PublishInitialInput): Promise<PublishedInitial> {
  verifyApproval(input.candidate, input.approval);
  if (input.candidate.filename !== managedRevisionFilename('ROOT', 1) || input.candidate.revision !== artifact.revisionLabel(1) || input.candidate.bytes.length === 0) throw new Error('INVALID_INITIAL_CANDIDATE');
  const operationId = input.operationId ?? this.operationIdFactory();
  let published = false;
  const guardEvidence: Record<string, unknown> = {};
  try {
   guardEvidence.begin = requireAllowed(await this.guard.execute({ action: 'begin_document_operation', operation_id: operationId }), 'BEGIN');
   guardEvidence.preflight = requireAllowed(await this.guard.execute({ action: 'preflight_plan', operation_id: operationId, mode: 'INITIAL_CREATE', budget: { max_document_delegations: 0, attempts: 1, model_candidates: 0, patches: 0 }, targetFilename: input.candidate.filename, mutationAction: 'write' }), 'PREFLIGHT');
   const authorization = requireAllowed(await this.guard.execute({ action: 'authorize_mutation', operation_id: operationId }), 'AUTHORIZE');
   if (!authorization.authorization) throw new Error('MUTATION_AUTHORIZATION_MISSING');
   guardEvidence.authorization = authorization;
   const created = await this.workspace.execute(operationId, { action: 'write', resource: 'proposal', slug: artifact.revisionLabel(1), content: input.candidate.bytes.toString('utf8'), operation_id: operationId, operationAuthorization: authorization.authorization } as ProposalWorkspaceInput);
   published = true;
   const actual = String(created.details.target ?? '').replace(new RegExp(`^${artifact.directory}/`), '');
   const publishedSha256 = String(created.details.targetSha256 ?? created.details.sha256 ?? '');
   if (actual !== input.candidate.filename) throw new Error('UNEXPECTED_PUBLISHED_TARGET');
   const reread = await this.workspace.execute(operationId, { action: 'read', resource: 'managed_target', name: actual });
   const publishedBytes = managedBytes(reread);
   const completion = created.details.operationGuard;
   if (!completion || typeof completion !== 'object') throw new Error('INITIAL_GUARD_COMPLETION_MISSING');
   guardEvidence.complete = requireAllowed(completion, 'COMPLETE');
   if (String(reread.details.sha256 ?? '') !== publishedSha256 || sha256(publishedBytes) !== publishedSha256 || !publishedBytes.subarray(-input.candidate.bytes.length).equals(input.candidate.bytes)) throw new Error('PUBLISHED_READ_MISMATCH');
   return { operationId, targetFilename: managedRevisionFilename('ROOT', 1), targetRevision: artifact.revisionLabel(1), publishedSha256, publishedBytes, candidateDigest: input.candidate.digest, workspaceEvidence: { create: created.details, read: reread.details }, guardEvidence };
  } catch (error) {
   if (!published) { try { guardEvidence.block = await this.guard.execute({ action: 'block_operation', operation_id: operationId, reason: error instanceof Error ? error.message : String(error) }); } catch {} }
   throw Object.assign(error instanceof Error ? error : new Error(String(error)), { published, operationId, guardEvidence });
  }
 }

 /** Existing direct-document successor publication contract; unchanged for its callers. */
 async publishSuccessor(input: PublishSuccessorInput): Promise<PublishedSuccessor> {
  const profile = input.effectiveOperationProfile; if (!profile || profile.intent !== input.intent || profile.cleanupLevel !== input.cleanupLevel) throw new Error('INVALID_EFFECTIVE_OPERATION_PROFILE');
  if (!strictManagedRevision(input.sourceFilename) || !/^[a-f0-9]{64}$/.test(input.sourceSha256) || !Array.isArray(input.patches) || input.patches.length < 1) throw new Error('INVALID_SUCCESSOR_INPUT');
  if (input.modelCalls < 0 || input.plannerCalls < 0 || input.roleAuthorizations < 0 || input.modelCalls > profile.maxModelCalls || input.plannerCalls > profile.maxPlannerCalls || input.roleAuthorizations > profile.maxRoleAuthorizations || input.patches.length > profile.maxPatchCount || profile.maxMutations < 1) throw new Error('INVALID_OPERATION_BUDGET');
  const patches = input.patches; const targetFilename = nextSuccessorTarget(input.sourceFilename); const targetRevisionLabel = parseManagedRevision(targetFilename)?.revision; if (!targetRevisionLabel) throw new Error('INVALID_TARGET_REVISION');
  const operationId = input.operationId ?? this.operationIdFactory(); let published = false; const guardEvidence: Record<string, unknown> = {};
  try {
   guardEvidence.begin = requireAllowed(await this.guard.execute({ action: 'begin_document_operation', operation_id: operationId }), 'BEGIN');
   guardEvidence.preflight = requireAllowed(await this.guard.execute({ action: 'preflight_plan', operation_id: operationId, mode: 'INCREMENTAL_EDIT', operation: input.intent, budget: { max_document_delegations: input.roleAuthorizations, attempts: 1, model_candidates: input.modelCalls, patches: input.patches.length }, sourceFilename: input.sourceFilename, sourceSha256: input.sourceSha256, successorFilename: targetFilename, mutationAction: 'derive_successor' }), 'PREFLIGHT');
   const authorization = requireAllowed(await this.guard.execute({ action: 'authorize_mutation', operation_id: operationId }), 'AUTHORIZE'); if (!authorization.authorization) throw new Error('MUTATION_AUTHORIZATION_MISSING'); guardEvidence.authorization = authorization;
   const derived = await this.workspace.execute(operationId, { action: 'derive_successor', resource: 'proposal', source: input.sourceFilename, sourceSha256: input.sourceSha256, slug: targetFilename.slice(`${artifact.stem}-`.length, -'.md'.length), patches, operation_id: operationId, operationAuthorization: authorization.authorization } as ProposalWorkspaceInput); published = true;
   const details = derived.details; const actual = String(details.target ?? '').replace(new RegExp(`^${artifact.directory}/`), ''); if (actual !== targetFilename) throw new Error('UNEXPECTED_PUBLISHED_TARGET');
   const publishedSha = String(details.targetSha256 ?? details.sha256 ?? ''); const reread = await this.workspace.execute(operationId, { action: 'read', resource: 'managed_target', name: actual }); const bytes = managedBytes(reread); const readSha = String(reread.details.sha256 ?? '');
   const source = await this.workspace.execute(operationId, { action: 'read', resource: 'managed_target', name: input.sourceFilename }); if (String(source.details.sha256 ?? '') !== input.sourceSha256) throw new Error('SOURCE_CHANGED_AFTER_PUBLISH');
   if (!strictRevisionLabel(targetRevisionLabel) || publishedSha !== readSha || sha256(bytes) !== readSha) throw new Error(`PUBLISHED_READ_MISMATCH:${publishedSha}:${readSha}:${sha256(bytes)}`);
   guardEvidence.complete = requireAllowed(await this.guard.execute({ action: 'complete_operation', operation_id: operationId }), 'COMPLETE');
   return { operationId, sourceFilename: input.sourceFilename, sourceSha256: input.sourceSha256, targetFilename: actual, targetRevision: targetRevisionLabel, publishedSha256: readSha, publishedBytes: bytes, patchCount: input.patches.length, workspaceEvidence: { derive: details, read: reread.details, source: source.details }, guardEvidence };
  } catch (error) { if (!published) { try { guardEvidence.block = await this.guard.execute({ action: 'block_operation', operation_id: operationId, reason: error instanceof Error ? error.message : String(error) }); } catch {} } throw Object.assign(error instanceof Error ? error : new Error(String(error)), { published, operationId, guardEvidence }); }
 }

 /** Scientific successor path requires approval but delegates the guarded write to the unchanged V2 method. */
 async publishApprovedSuccessor(input: PublishApprovedSuccessorInput): Promise<PublishedSuccessor> {
  verifyApproval(input.candidate, input.approval);
  const published = await this.publishSuccessor(input);
  if (!published.publishedBytes.equals(input.candidate.bytes)) throw new Error('PUBLISHED_CANDIDATE_MISMATCH');
  return published;
 }
}
