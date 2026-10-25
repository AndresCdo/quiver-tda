import { sha256, type LocalContext } from './types.js';
import type { CandidateValidation, ExactDocumentCandidate } from './revision-domain.js';
import type { MaterializationClaimProvenance, MaterializationPlan } from './revision-domain.js';
import type { ReviewerAdapter, ReviewerAssessment } from './reviewer-adapter.js';
import { validateReviewerAssessment } from './reviewer-adapter.js';

export type DocumentReviewApproval = Readonly<{
	decision: 'APPROVE';
	candidateDigest: string;
	planDigest: string;
}>;
export type DocumentReviewResult =
	| { status: 'approved'; approval: DocumentReviewApproval }
	| { status: 'non_pass'; decision: Exclude<ReviewerAssessment['decision'], 'APPROVE'> };

/**
 * The Document Reviewer sees immutable candidate evidence and has no capability to alter it.
 * Only its exact APPROVE result can be handed to a guarded publication adapter.
 */
export class DocumentReviewerGate {
	constructor(private readonly reviewer: ReviewerAdapter) {}

	async review(input: Readonly<{ candidate: ExactDocumentCandidate; plan: MaterializationPlan; provenance: readonly MaterializationClaimProvenance[]; validation: CandidateValidation }>): Promise<DocumentReviewResult> {
		if (sha256(input.candidate.bytes) !== input.candidate.digest || input.candidate.digest !== input.validation.candidateDocumentSha256 || input.plan.digest !== input.validation.planDigest || !Array.isArray(input.provenance) || input.provenance.length !== input.plan.claimProvenance.length) {
			throw new Error('DOCUMENT_REVIEW_INPUT_INVALID');
		}
		const context: LocalContext = {
			documentSha256: input.candidate.digest,
			targetEntryId: input.candidate.filename,
			instruction: 'Review the exact frozen materialization candidate without changing it.',
			fragments: [{ entryId: input.candidate.filename, type: 'document', text: input.candidate.bytes.toString('utf8'), textSha256: input.candidate.digest, headingPath: [] }],
			nearbySymbols: {},
			directReferences: input.provenance.map((claim) => `scientific-decision:${claim.decisionId}`),
			maxBytes: input.candidate.bytes.length,
		};
		const assessment = validateReviewerAssessment(await this.reviewer.review({
			instruction: context.instruction,
			context,
			plan: Object.freeze({ plan: input.plan, candidate: { filename: input.candidate.filename, revision: input.candidate.revision, digest: input.candidate.digest }, provenance: structuredClone(input.provenance), validation: structuredClone(input.validation) }),
		}));
		if (assessment.decision !== 'APPROVE') return { status: 'non_pass', decision: assessment.decision };
		return { status: 'approved', approval: Object.freeze({ decision: 'APPROVE', candidateDigest: input.candidate.digest, planDigest: input.plan.digest }) };
	}
}
