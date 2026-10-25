import type { CompiledPatch, EditAction, EditPlan } from './types.js';
import type { ManagedRevisionName } from './artifact-naming.js';

/**
 * The vocabulary of a managed revision: what a revision is, what it was published from,
 * and the frozen payload that produced it. Everything here is reachable from the ordinary
 * publication path (CREATE_INITIAL_REVISION and CREATE_SUCCESSOR) and stays reachable
 * whether or not a durable deliberation record exists alongside it.
 */

/** Opaque identifiers minted by whatever recorded the decision a revision claims to carry. */
export type ScientificThreadId = string;
export type ScientificDecisionId = string;
export type ScientificEventId = string;

export type RevisionEvidence = {
	filename: string;
	revision: string;
	/** Stable lifecycle-v1 identity when this is explicit authority rather than a legacy projection. */
	revisionId?: string;
	baseDocumentId?: string;
	lineage?: { sourceKind: 'BASE_DOCUMENT'|'REVISION'; sourceId: string; sourceContentHash: string };
	documentSha256: string;
};

export type MaterializationPlanKind = 'CREATE_R01' | 'CREATE_SUCCESSOR';

export type FrozenDecisionSelection = {
	policyVersion: 1;
	decisionIds: ScientificDecisionId[];
	acceptedEventIds: ScientificEventId[];
	selectionKey: string;
};

export type MaterializationClaimProvenance = {
	claimId: string;
	decisionId: ScientificDecisionId;
	threadId: ScientificThreadId;
	acceptedEventId: ScientificEventId;
	acceptedSynthesisDigest: string;
	summary: string;
	/** Present only when the accepted decision carries a real, single-locus structured edit (see `parseProposedEdit`). Absent decisions fall back to the pre-existing summary annotation. */
	proposedEdit?: EditAction;
};

export type CanonicalProposalMetadata = {
	schemaVersion: 1;
	title: string;
	sectionHeading: string;
};

export type FrozenPatchPreconditions = {
	expectedRevision: RevisionEvidence;
	baseDocumentSha256: string;
	anchorEntryId: string;
	anchorTextSha256: string;
};

export type FrozenEditPlan = {
	order: number;
	plan: EditPlan;
	preconditions: FrozenPatchPreconditions;
};

export type CreateR01PayloadV1 = {
	kind: 'CREATE_R01';
	payloadVersion: 1;
	markdown: string;
	/**
	 * `filename` was a fixed-stem-and-first-revision literal string type -- a TypeScript literal cannot
	 * depend on a runtime profile value, so widening it to plain `string` would delete this
	 * compile-time check with nothing announcing the loss. `ManagedRevisionName` (not the
	 * lineage-mandatory `ManagedInitialName`) is correct here: this fixed-base bootstrap route's
	 * target is always the ROOT-lineage first revision, which `strictManagedRevision` accepts.
	 */
	/** `revision` was the literal `'r01'` beside it, which no runtime profile value can satisfy: it is `artifact.revisionLabel(1)`, spelled `v01` under a domain whose revision prefix is `v`. Plain `string`, with the runtime guard in the test suite. */
	target: { filename: ManagedRevisionName; revision: string };
	canonicalMetadata: CanonicalProposalMetadata;
};

export type CreateSuccessorPayloadV1 = {
	kind: 'CREATE_SUCCESSOR';
	payloadVersion: 1;
	expectedBase: RevisionEvidence;
	patches: readonly FrozenEditPlan[];
};

/** A revision rendered in memory from a plan, before anything is written. */
export type ExactDocumentCandidate = {
	filename: string;
	revision: string;
	bytes: Buffer;
	digest: string;
	/** Present only for successor publication; produced while executing frozen patches in memory. */
	patches?: CompiledPatch[];
};

export type CandidateValidation = {
	operation: MaterializationPlan['operation'];
	planDigest: string;
	payloadVersion: 1;
	inputDocumentSha256?: string;
	candidateDocumentSha256: string;
	patchIds: string[];
	validationResults: Record<string, boolean>;
};

export type MaterializationPlan = {
	schemaVersion: 1;
	materializationId: string;
	selectionKey: string;
	operation: MaterializationPlanKind;
	frozenSelection: FrozenDecisionSelection;
	source?: RevisionEvidence;
	expectedRevisionIdentity?: RevisionEvidence;
	payload: CreateR01PayloadV1 | CreateSuccessorPayloadV1;
	claimProvenance: MaterializationClaimProvenance[];
	digest: string;
};
