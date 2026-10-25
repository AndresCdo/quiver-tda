import { createHash } from 'node:crypto';

// Bumped for change 6 (`table`/`figure_placeholder` first-class entries): retyping a GFM
// table from `paragraph` to `table` changes its entryId (`${type}:${sha256(...)}`), so this
// is a genuine re-parse, not a same-output rename -- it must NOT be added to
// `SUPERSEDED_PARSER_VERSIONS` below (see that constant's own doc comment).
// The generation stays `2`: this engine's parsing did not change. Only the
// namespace did, from the skill it was extracted from to what it actually is --
// a domain-neutral deliberation engine that reads which domain it serves off a
// host-chosen profile. That rename is precisely the case `SUPERSEDED_PARSER_
// VERSIONS` below exists for, and the old spelling is listed there.
export const PARSER_VERSION = 'deliberation/2';
/**
 * Identifiers this parser answered to before, which derived state committed under them may still carry.
 *
 * The version exists to invalidate stored state when PARSING changes, so it may only be widened when
 * the change was demonstrably a rename. `paper-proposal/1` qualifies: the commit that introduced the
 * current name (691d9a2) moved every index module — block plan, document, reference, symbol, concept —
 * with zero line changes, and edited exactly this constant. State written under the old name was
 * produced by byte-identical parsing code, so rejecting it invalidated correct history.
 *
 * The second entry qualifies on the identical grounds: the engine's parsing is byte-for-byte unchanged
 * by the rename that produced `deliberation/2` — that change edited this constant, comments, and
 * infrastructure identifiers, and not one line of any index module. State written under the old name
 * was produced by the same parsing code, so rejecting it would invalidate correct history over a
 * spelling.
 *
 * This comment does not spell that entry, and the omission is deliberate: the core-scan lock
 * (`no file in the shared core names any domain`) exempts the list itself, because a superseded-
 * identifier list cannot do its job without naming what it supersedes — and exempts nothing else in
 * this file, so the same name written one line up is still a leak. Read the entry from the array.
 *
 * Reads accept these; writes always record PARSER_VERSION.
 */
export const SUPERSEDED_PARSER_VERSIONS = Object.freeze(['paper-proposal/1', 'proposal-deliberation/2']);
export function isAcceptedParserVersion(stored: unknown, current: string = PARSER_VERSION): boolean {
	return stored === current || (typeof stored === 'string' && SUPERSEDED_PARSER_VERSIONS.includes(stored));
}
export const LIMITS = Object.freeze({ maxCandidates: 8, maxContextFragments: 8, maxContextBytesLocal: 32000, maxContextBytesSection: 32000, maxPatchCountLocal: 4, maxCleanupRanges: 3, maxModelCallsLocal: 1, maxModelCallsConceptual: 2, maxParallelReadTasks: 4, maxParallelValidationTasks: 6, maxParallelWriteTasks: 1 });
export type Intent = 'MODIFY'|'INSERT'|'DELETE'|'MOVE'|'COPY'|'CONCEPTUAL_REVISION'|'REVIEW'|'DELIBERATE'|'WITHDRAW_REVISION'|'RESTORE_WITHDRAWN_REVISION'|'CLOSE_DELIBERATION'|'AMBIGUOUS';
/** Explicit public route: derives the only permitted target from the managed source. */
export type CreateSuccessorOperation = 'CREATE_SUCCESSOR';
export type SuccessorEditIntent = Extract<Intent,'MODIFY'|'CONCEPTUAL_REVISION'>;
export type PublicV2Operation = RevisionLifecycleOperation|CreateSuccessorOperation;
export const PENDING_AUDIT_LEASE_MS = 30_000;
export type RevisionLifecycleOperation = Extract<Intent,'WITHDRAW_REVISION'|'RESTORE_WITHDRAWN_REVISION'>;
export type PendingAuditPhase = 'WITHDRAW_PUBLIC_ARTIFACTS_MOVED'|'RESTORE_PUBLIC_ARTIFACTS_MOVED';
export type PendingAuditArtifact = {
 publicRelativePath:string;
 sha256:string;
 expectedLocation:'quarantine-public-backup'|'public';
};
export type PendingAuditContext = {
 operationType:RevisionLifecycleOperation;
 operationId:string;
 pendingAudit:true;
 phase:PendingAuditPhase;
 temporarilyMovedArtifacts:PendingAuditArtifact[];
 expectedMarker:{
  relativePath:string;
  state:'PENDING_AUDIT';
  inventoryDigest:string;
  expiresAt:string;
 };
};
export type RevisionLifecycleLockOwner = Readonly<{
 operationId:string;
 filename:string;
}>;
export type RevisionLifecycleArtifact = {
 publicRelativePath:string;
 quarantineRelativePath:string;
 sha256:string;
};
export type RevisionWithdrawalMetadata = {
 schemaVersion:'1';
 operationId:string;
 operationTimestamp:string;
 requestedFilename:string;
 revision:string;
 documentSha256:string;
 sourceRevision:string;
 sourceFilename:string;
 reason:string;
 artifacts:RevisionLifecycleArtifact[];
 inventoryDigest:string;
 preWithdrawalLatestFilename:string;
};
export type RevisionLifecycleResult = {
 status:'withdrawn'|'restored'|'blocked';
 operation:RevisionLifecycleOperation;
 withdrawnFilename:string|null;
 restoredLatestFilename:string|null;
 artifactCount:number;
 backupLocation:string|null;
 auditStatus:'PASS'|'WARN'|'FAIL'|'NOT_RUN';
 selfAuditStatus:'PASS'|'WARN'|'FAIL'|'NOT_RUN';
 warnings:string[];
};
export type EntryType = 'document'|'section'|'subsection'|'heading'|'paragraph'|'display_equation'|'inline_math_region'|'list'|'code_block'|'definition'|'theorem'|'algorithm'|'table'|'figure_placeholder'|'composite';
export type Position = 'before'|'after'|'inside_start'|'inside_end';
export type DerivedStateStatus = 'VALID'|'STALE'|'MISSING'|'BUILDING'|'FAILED'|'COMMITTED';
export type CleanupLevel = 'NONE'|'STRUCTURAL'|'SEMANTIC'; export type MoveMode = 'LITERAL'|'ADAPTIVE';
export const sha256 = (value: string | Buffer) => createHash('sha256').update(value).digest('hex');
/**
 * The preservation gate's domain-neutral vocabulary (change 4): an atom is anything a
 * profile's own extractor recognizes as something that must not vanish silently,
 * whatever the domain calls it. `kind` is intentionally a bare `string`: only the
 * profile knows what its own atom kinds are.
 */
export type PreservationAtomKind = string;
export type PreservationAtom = { id: string; kind: PreservationAtomKind; text: string };
export type PreservationDelta = { lost: PreservationAtom[]; added: PreservationAtom[] };
export type PreservationViolation = { rule: string; line: number; detail: string };
export type StructuralEntry = { entryId:string; type:EntryType; startByte:number; endByte:number; textSha256:string; parentId?:string; childIds:string[]; ordinal:number; headingPath:string[]; labels:string[]; tags:string[]; lexicalTerms:string[]; deterministicAliases:string[]; neighboringEntryIds:string[]; sectionReplacement?:SectionReplacementContract };
export type StructuralIndex = { entries: StructuralEntry[]; byId: Record<string, StructuralEntry> };
export type ReferenceIndex = { labels:Record<string,string>; tags:Record<string,string>; references:{kind:string; value:string; entryId:string}[]; missing:string[]; duplicates:string[] };
export type SymbolIndex = { symbols:Record<string,{normalized:string; definition?:string; domain?:string; firstEntryId:string; uses:string[]; section:string[]}>; conflicts:string[] };
export type ConceptIndex = { terms:Record<string,string[]>; aliases:Record<string,string[]> };
export type DerivedStateManifest = { schemaVersion:'1'; parserVersion:string; documentFilename:string; documentSha256:string; structuralIndexSha256:string; referenceIndexSha256:string; symbolIndexSha256:string; conceptIndexSha256:string; createdAt:string; status:DerivedStateStatus; revision:string };
export type DocumentState = { filename:string; revision:string; lineage:string; documentSha256:string; documentBytes:Buffer; parserVersion:string; structuralIndex:StructuralIndex; referenceIndex:ReferenceIndex; symbolIndex:SymbolIndex; conceptIndex:ConceptIndex; derivedStateStatus:DerivedStateStatus; derivedStateManifest:DerivedStateManifest };
export type UserRequest = { instruction:string; selectedEntryId?:string; model?: EditModel; operationId?:string };
export type FidelityConstraints = { targetBlock?:string; replacementBlock?:string; preserveExternalBytes?:true; noReformat?:true; noSemanticReinterpretation?:true };
export type ResolvedIntent = { intent:Intent; targetDescription:string; sourceDescription?:string; destinationDescription?:string; requestedPosition?:Position; requestedEffect?:string; semanticChange:boolean; constraints:string[]; fidelity:FidelityConstraints; scope:'LOCAL'|'SECTION'|'DOCUMENT'; evidence:string[]; destructiveIntent:boolean; cleanupAuthorized:boolean; moveMode:MoveMode; removeSource:boolean; cleanupLevel:CleanupLevel; modelBudget:number; confidence:number; pendingQuestions:string[]; unresolvedQuestions:string[] };
export type SectionReplacementContract = { kind:'numbered-section-range'; startByte:number; endByte:number; newline:'\n'|'\r\n'; startAtLineStart:true; endAfterCompleteLine:true; requestedSectionIds:string[] };
export type CompositeTarget = { entryIds:string[]; startByte:number; endByte:number; documentSha256:string; textSha256:string; exactProvidedText:string; sectionReplacement?:SectionReplacementContract };
export type TargetCandidate = { entryId:string; type:EntryType; headingPath:string[]; matchedTerms:string[]; matchedLabels:string[]; matchedTags:string[]; matchedSymbols:string[]; score:number; confidence:number; shortPreview:string; evidence:string[]; composite?:CompositeTarget; /** ATX level of a heading locus (successor resolution only). */ headingLevel?:number };
export type ContextFragment = { entryId:string; type:EntryType; text:string; textSha256:string; headingPath:string[] };
export type LocalContext = { documentSha256:string; targetEntryId:string; instruction:string; fragments:ContextFragment[]; nearbySymbols:Record<string,string>; directReferences:string[]; fidelity?:FidelityConstraints; maxBytes?:number; authorizedEntryIds?:string[]; successorCompositeTarget?:true; successorRangeEntryIds?:string[] };
export type MoveCopyContext = { documentSha256:string; instruction:string; sourceContext:LocalContext; destinationContext:LocalContext; fragments:ContextFragment[] };
export type EditAction = { kind:'replace'; targetEntryId:string; replacementText:string; semanticChange?:boolean; rationale?:string } | { kind:'insert'; anchorEntryId:string; position:Position; content:string } | { kind:'delete'; targetEntryId:string; instructionEvidence:string; reason:string } | { kind:'move'|'copy'; sourceEntryIds:string[]; destinationAnchorId:string; position:Position; moveMode:MoveMode; removeSource:boolean; transformedContent?:string; cleanupLevel:CleanupLevel } | { kind:'cleanup'; boundedRangeIds:string[]; action:'delete'|'rewrite'; reason:string; instructionEvidence:string } | { kind:'rewrite_transition'; boundedRangeId:string; replacementText:string; reason:string };

/**
 * The public byte cap for a persisted scientific `proposedEdit.replacementText`
 * (or `.content`) leaf ONLY. Every other public payload string (including every
 * OTHER field nested inside `proposedEdit` itself) stays bounded at the
 * pre-existing 2,000-byte guard -- see the durable-state
 * `assertPublicValue`, which is the sole enforcement point.
 */
export const PROPOSED_EDIT_REPLACEMENT_MAX_BYTES = 20_000;

const PROPOSED_EDIT_INSERT_POSITIONS = new Set<Position>(['before', 'after', 'inside_start', 'inside_end']);
const PROPOSED_EDIT_CLEANUP_LEVELS = new Set<CleanupLevel>(['NONE', 'STRUCTURAL', 'SEMANTIC']);

/**
 * Validates an untrusted, persisted `TUTOR_ASSESSED.payload.proposedEdit` value
 * into a genuine `EditAction`. Recognizes five bounded, single-locus shapes:
 * `replace` (a CHANGE), `insert` (an ADD anchored at one existing entry's
 * boundary), `delete` (a REMOVE of one existing entry's span), and `move`/
 * `copy` (a RELOCATION -- exactly one source entry to one destination anchor)
 * -- the only shapes `ScientificWorkflowService.candidate()` ever emits.
 * Anything else (a malformed object, or a well-formed but unimplemented
 * `cleanup`/`rewrite_transition` shape) returns `undefined` so callers fall
 * back to the pre-existing summary-annotation route rather than trusting an
 * edit shape this pipeline never validated end-to-end.
 *
 * `move`/`copy` bound `sourceEntryIds` to exactly one entry for this slice
 * (multi-entry relocation sources remain a documented, unforced fallback, same
 * as multi-entry-per-decision elsewhere in this pipeline). `removeSource` must
 * agree with `kind` (`move` implies `true`, `copy` implies `false`) -- a
 * mismatched combination is rejected as malformed rather than silently
 * trusted. `transformedContent` is REQUIRED and bounded when `moveMode` is
 * `'ADAPTIVE'` (never fabricated downstream if absent) and, when present for a
 * `'LITERAL'` move/copy, is simply ignored by every resolver (LITERAL content
 * always comes from the frozen source bytes, never from this field).
 */
export function parseProposedEdit(value: unknown): EditAction | undefined {
	if (!value || typeof value !== 'object') return undefined;
	const candidate = value as Record<string, unknown>;
	if (candidate.kind === 'replace') {
		if (typeof candidate.targetEntryId !== 'string' || candidate.targetEntryId.length === 0 || candidate.targetEntryId.length > 128) return undefined;
		if (typeof candidate.replacementText !== 'string' || candidate.replacementText.length === 0 || candidate.replacementText.length > PROPOSED_EDIT_REPLACEMENT_MAX_BYTES) return undefined;
		if (candidate.semanticChange !== undefined && typeof candidate.semanticChange !== 'boolean') return undefined;
		if (candidate.rationale !== undefined && (typeof candidate.rationale !== 'string' || candidate.rationale.length > 2_000)) return undefined;
		return {
			kind: 'replace',
			targetEntryId: candidate.targetEntryId,
			replacementText: candidate.replacementText,
			...(candidate.semanticChange !== undefined ? { semanticChange: candidate.semanticChange as boolean } : {}),
			...(candidate.rationale !== undefined ? { rationale: candidate.rationale as string } : {}),
		};
	}
	if (candidate.kind === 'insert') {
		if (typeof candidate.anchorEntryId !== 'string' || candidate.anchorEntryId.length === 0 || candidate.anchorEntryId.length > 128) return undefined;
		if (typeof candidate.position !== 'string' || !PROPOSED_EDIT_INSERT_POSITIONS.has(candidate.position as Position)) return undefined;
		if (typeof candidate.content !== 'string' || candidate.content.length === 0 || candidate.content.length > PROPOSED_EDIT_REPLACEMENT_MAX_BYTES) return undefined;
		return { kind: 'insert', anchorEntryId: candidate.anchorEntryId, position: candidate.position as Position, content: candidate.content };
	}
	if (candidate.kind === 'delete') {
		if (typeof candidate.targetEntryId !== 'string' || candidate.targetEntryId.length === 0 || candidate.targetEntryId.length > 128) return undefined;
		if (typeof candidate.instructionEvidence !== 'string' || candidate.instructionEvidence.length === 0 || candidate.instructionEvidence.length > 2_000) return undefined;
		if (typeof candidate.reason !== 'string' || candidate.reason.length === 0 || candidate.reason.length > 2_000) return undefined;
		return { kind: 'delete', targetEntryId: candidate.targetEntryId, instructionEvidence: candidate.instructionEvidence, reason: candidate.reason };
	}
	if (candidate.kind === 'move' || candidate.kind === 'copy') {
		if (!Array.isArray(candidate.sourceEntryIds) || candidate.sourceEntryIds.length !== 1) return undefined;
		const sourceEntryId = candidate.sourceEntryIds[0];
		if (typeof sourceEntryId !== 'string' || sourceEntryId.length === 0 || sourceEntryId.length > 128) return undefined;
		if (typeof candidate.destinationAnchorId !== 'string' || candidate.destinationAnchorId.length === 0 || candidate.destinationAnchorId.length > 128) return undefined;
		if (typeof candidate.position !== 'string' || !PROPOSED_EDIT_INSERT_POSITIONS.has(candidate.position as Position)) return undefined;
		if (candidate.moveMode !== 'LITERAL' && candidate.moveMode !== 'ADAPTIVE') return undefined;
		if (typeof candidate.removeSource !== 'boolean' || candidate.removeSource !== (candidate.kind === 'move')) return undefined;
		if (typeof candidate.cleanupLevel !== 'string' || !PROPOSED_EDIT_CLEANUP_LEVELS.has(candidate.cleanupLevel as CleanupLevel)) return undefined;
		if (candidate.transformedContent !== undefined && (typeof candidate.transformedContent !== 'string' || candidate.transformedContent.length === 0 || candidate.transformedContent.length > PROPOSED_EDIT_REPLACEMENT_MAX_BYTES)) return undefined;
		if (candidate.moveMode === 'ADAPTIVE' && candidate.transformedContent === undefined) return undefined;
		return {
			kind: candidate.kind,
			sourceEntryIds: [sourceEntryId],
			destinationAnchorId: candidate.destinationAnchorId,
			position: candidate.position as Position,
			moveMode: candidate.moveMode,
			removeSource: candidate.removeSource,
			cleanupLevel: candidate.cleanupLevel as CleanupLevel,
			...(candidate.transformedContent !== undefined ? { transformedContent: candidate.transformedContent as string } : {}),
		};
	}
	return undefined;
}
export type DeletePlan = { planVersion:'2'; documentSha256:string; targetEntryIds:string[]; destructiveIntent:true; instructionEvidence:string[]; reason:string; affectedReferences:string[]; affectedSymbols:string[]; cleanupLevel:CleanupLevel; unresolvedQuestions:string[] };
export type EditPlan = { planVersion:'2'; documentSha256:string; intent:Intent; instructionHash:string; resolvedTargets:string[]; destination?:string; semanticChange:boolean; destructiveIntent:boolean; cleanupLevel:CleanupLevel; constraints:string[]; actions:EditAction[]; expectedEffects:string[]; unresolvedQuestions:string[]; successorCompositeTarget?:true };
export type MovePlan = EditPlan & { intent:'MOVE'; sourceEntryIds:string[]; destinationEntryId:string; position:Position; mode:MoveMode; removeSource:true; transformedContent?:string; semanticChange:boolean };
export type CopyPlan = EditPlan & { intent:'COPY'; sourceEntryIds:string[]; destinationEntryId:string; position:Position; mode:MoveMode; removeSource:false; transformedContent?:string; semanticChange:boolean };
export type StructuralPatchSelector = {entryId:string;startByte:number;endByte:number;textSha256:string;documentSha256:string};
export type CompiledPatch = { id:string; kind:'replace'|'insert'; oldText?:string; newText?:string; anchor?:string; position?:'before'|'after'; content?:string; selector?:StructuralPatchSelector };
export type Compilation = { patches:CompiledPatch[]; candidate:string; candidateSha256:string; patchIds:string[]; unchangedByteCoverage:boolean; modifiedRanges:{startByte:number;endByte:number}[]; sourceBytes?:Buffer; destinationEntryId?:string; position?:Position };
export type SemanticPlannerInput = { intent:ResolvedIntent; instruction:string; target?:TargetCandidate; context?:LocalContext; sourceContext?:LocalContext; destinationContext?:LocalContext; sourceEntryIds?:string[]; destinationEntryId?:string; position?:Position; constraints:string[]; fidelity?:FidelityConstraints; documentSha256:string };
export type PlannerInputBudgetEvidence = { unit:'utf8_bytes'; accountingVersion:'1'; payloadPath:'fidelity_modify'; effectiveBytes:number; budgetBytes:number };
export type SemanticEditPlanner = {
 preflight?(input:SemanticPlannerInput):PlannerInputBudgetEvidence|undefined;
 plan(input:SemanticPlannerInput):Promise<Partial<EditPlan>&{transformedContent?:string; sourceEntryIds?:string[]; destinationEntryId?:string; position?:Position; actions?:EditAction[]}>;
};
export type EditModel = { plan?(input:any):Promise<Partial<EditPlan>>; validate?(input:{plan:EditPlan; candidate:string}):Promise<{ok:boolean; reason?:string}> };
export type RevisionReceipt = { sourceRevision:string; targetRevision:string; sourceFilename:string; targetFilename:string; intent:Intent; operation:Intent|CreateSuccessorOperation; instructionHash:string; /** Optional, recorded as supplied on the publishing request: why the change was made. Absent on every receipt written without it, including all receipts before 0.14.0. */ rationale?:string; /** Optional, recorded as supplied: who took the decision, `agent` or `human`. Absent when not supplied. */ decider?:'agent'|'human'; documentShaBefore:string; documentShaAfter:string; resolvedEntryIds:string[]; patchIds:string[]; patchCount:number; cleanupLevel:CleanupLevel; derivedStateStatus:DerivedStateStatus; modelCalls:number; roleAuthorizations:number; inputTokens:number; outputTokens:number; elapsedMs:number; parallelTasks:number; validationResults:Record<string,boolean>; /** Change 8, option (b): the header block is overwritten each version, so the receipt chain is where full change-summary history lives. Present only when `profile.artifact.changeHeader` is declared and the caller supplied one. */ changeSummary?:{what:string;why:string}; /** References in the successor to companion artifacts named after another revision (`artifact-naming.ts` `staleCompanionReferences`). Present only when one exists; receipts written before it carry no key and read unchanged. */ staleCompanionReferences?:{reference:string;revision:string;inherited:boolean}[] };
export type OperationRisk='LOW'|'MEDIUM'|'HIGH';
export type EffectiveOperationProfile={intent:Intent;cleanupLevel:CleanupLevel;maxModelCalls:number;maxPlannerCalls:number;maxRoleAuthorizations:number;maxMutations:number;maxPatchCount:number;maxCleanupRanges:number;requiresTutor:boolean;requiresReviewer:boolean;operationRisk:OperationRisk};
export type LifecycleV1RecordState='ACTIVE'|'SUPERSEDED'|'WITHDRAWN';
export type LifecycleV1WorkspaceState='EMPTY'|'BASE_REGISTERED'|'ACTIVE'|'WITHDRAWN_ONLY'|'INCONSISTENT';
export type LifecycleV1ErrorCode='BASE_DOCUMENT_NOT_REGISTERED'|'BASE_DOCUMENT_ALREADY_REGISTERED'|'ACTIVE_REVISION_ALREADY_EXISTS'|'ACTIVE_REVISION_NOT_FOUND'|'INVALID_LINEAGE_REFERENCE'|'REVISION_NOT_WITHDRAWABLE'|'REVISION_NOT_WITHDRAWN'|'WITHDRAWAL_IDENTITY_NOT_FOUND'|'BASE_DOCUMENT_NOT_RESTORABLE'|'OUTPUT_FILENAME_CONFLICT'|'SOURCE_CONTENT_HASH_MISMATCH'|'LIFECYCLE_INVENTORY_INCONSISTENT'|'LIFECYCLE_V1_UNREGISTERED'|'REQUEST_ID_CONFLICT'|'RECOVERY_REQUIRED';
export type LineageReference={sourceKind:'BASE_DOCUMENT'|'REVISION';sourceId:string;sourceContentHash:string;baseDocumentId:string};
export type BaseDocument={schemaVersion:'lifecycle-v1';workspaceId:string;baseDocumentId:string;contentHash:string;content:string;provenance?:string;locator?:string;transitionId:string};
export type LifecycleRevision={schemaVersion:'lifecycle-v1';workspaceId:string;revisionId:string;baseDocumentId:string;contentHash:string;content:string;lineage:LineageReference;locator?:string;isFirst:boolean;transitionId:string};
export type WithdrawalRecord={schemaVersion:'lifecycle-v1';workspaceId:string;withdrawalId:string;revisionId:string;contentHash:string;recoveryContent:string;reason?:string;transitionId:string;state:'COMMITTED'|'RESTORED'|'ABORTED'};
export type MaterializationRequest={requestId:string;workspaceId:string;operation:'CREATE_FROM_BASE'|'CREATE_SUCCESSOR';source:LineageReference;approvedChanges:ReadonlyArray<{from:string;to:string}>;revisionId:string;locator?:string};
export type MaterializationResult={resultId:string;requestId:string;workspaceId:string;operation:'CREATE_FROM_BASE'|'CREATE_SUCCESSOR';revisionId:string;contentHash:string;source:LineageReference;outcome:'COMMITTED'|'ALREADY_COMMITTED'|'REJECTED'|'INCONSISTENT'|'RECOVERY_REQUIRED';code?:LifecycleV1ErrorCode;transitionId?:string};
export type WorkspaceLifecycleState={schemaVersion:'lifecycle-v1';workspaceId:string;lifecycleState:LifecycleV1WorkspaceState;base?:BaseDocument;revisions:Array<LifecycleRevision&{state:LifecycleV1RecordState}>;withdrawals:WithdrawalRecord[];activeRevisionId?:string;integrityDigest:string};
export type LifecycleTransitionEvidence={schemaVersion:'lifecycle-v1';transitionId:string;workspaceId:string;sequence:number;operation:string;requestId:string;outcome:'COMMITTED'|'REJECTED'|'RECOVERY_REQUIRED';recordPaths:string[];stateChanges:Array<{revisionId:string;state:LifecycleV1RecordState}>;committedAt:string};
export type { RevisionEvidence, CanonicalProposalMetadata, CreateR01PayloadV1, CreateSuccessorPayloadV1, MaterializationClaimProvenance, MaterializationPlan, MaterializationPlanKind, FrozenDecisionSelection, FrozenEditPlan, FrozenPatchPreconditions, CandidateValidation, ExactDocumentCandidate } from './revision-domain.js';
