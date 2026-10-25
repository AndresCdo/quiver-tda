import { randomUUID } from 'node:crypto';
import { MAX_CHAT_CONCLUSION_BYTES, MAX_CHAT_CONVERSATIONS, MAX_CHAT_TURNS, type PiSessionDraftRegistry } from './chat-draft-registry.js';
import { modelCall } from './runtime-metrics.js';
import type { DraftMaterializationPayload } from './draft-materialization.js';
import type { LocalContext } from './types.js';
import type { TutorAdapter, TutorAssessment } from './tutor-adapter.js';
import { validateTutorAssessment } from './tutor-adapter.js';
import type { ReviewerAdapter } from './reviewer-adapter.js';
import { validateReviewerAssessment } from './reviewer-adapter.js';
import { evaluateSuccessorGrowthThreshold, type GrowthThresholdVerdict } from './growth-threshold.js';

const MAX_CONTEXT_BYTES = 8_000;
export const MAX_CHAT_DOCUMENT_CONTEXT_BYTES = 6_000;
/** Bounds the paper-guide reference fragment (task 3.5/3.6, spec I2): loaded once at deliberation open, never reloaded per turn. */
export const MAX_CHAT_GUIDE_CONTEXT_BYTES = 4_000;
const CHAT_CONVERSATION_ID = /^chat-[a-z0-9][a-z0-9-]{0,250}$/;
const MAX_REPAIR_CYCLES = 2;
/** Default-on refute-loop trigger set (design decision R): only a concrete proposed change earns the full tutor->reviewer->repair loop. */
const CONCRETE_CHANGE_DECISIONS = new Set<TutorAssessment['decision']>(['ACCEPT_WITH_REVISIONS', 'PROPOSE_ALTERNATIVE']);

type ChatTurn = { conclusion: string; assessment: TutorAssessment };
/** One read-only paper-guide reference document (task 3.5/3.6, spec I2). Never mutated; loaded by the caller (proposal-workspace.ts), never read from disk by this session-local service. */
export type ChatGuideFragment = Readonly<{ path: string; content: string }>;
export type ChatDocumentContext = Readonly<{
	access: 'READ_ONLY';
	filename: string;
	revision: string;
	lineage: string;
	documentSha256: string;
	content: string;
	bytesRead: number;
	truncated: boolean;
}>;
/**
 * In-session-only accumulated deliberation state (design decision D-state).
 * `approvedSectionCount`/`approvedBytes` accumulate turn-by-turn ONLY while the
 * conversation is open and are discarded entirely on CLOSE (task 2.6/2.7) --
 * they never persist beyond the process/service instance and are never
 * written to any durable store.
 */
/**
 * Distinct approved-section identifiers accumulated so far (re-audit cleanup:
 * growth-threshold semantics count INDEPENDENT/disjoint section targets, not
 * approved turns -- see `approvedSectionIds` below for how each turn's
 * identifier is chosen).
 */
type Conversation = { turns: ChatTurn[]; document?: ChatDocumentContext; approvedSectionIds: ReadonlySet<string>; approvedBytes: number };
type RefuteOutcome = 'NOT_RUN' | 'ACCEPT' | 'REJECT' | 'NEEDS_CLARIFICATION' | 'REPAIR_EXHAUSTED';

export type ChatDeliberationResult = {
	status: 'deliberated' | 'blocked';
	conversationId: string;
	conclusion?: string;
	assessment?: TutorAssessment;
	alternatives: string[];
	risks: TutorAssessment['riskLevel'][];
	unresolvedQuestions: string[];
	context: { turnCount: number; reusedConclusion: boolean };
	modelCalls: number;
	tutorCalls: number;
	reviewerCalls: number;
	mutations: 0;
	receiptId: null;
	manifestStatus: 'NOT_PUBLISHED';
	auditStatus: 'NOT_RUN';
	selfAuditStatus: 'NOT_RUN';
	recoveryStatus: 'not_required';
	nextAction: null | 'clarify_request';
	reason?: string;
	/** Default-on bounded refute loop (design decision R / spec D3). Only present on a completed turn. */
	refute?: { ran: boolean; outcome: RefuteOutcome; repairCycles: number };
	/** Non-blocking growth advisory (task 2.10): recommends materializing a version once the in-session approved set grows past the threshold. Never blocks. */
	growthAdvisory?: GrowthThresholdVerdict;
};

export type CloseDeliberationResult = { status: 'closed' | 'not_open'; conversationId: string };

function boundedConclusion(value: string): string {
	return Buffer.from(value.trim()).subarray(0, MAX_CHAT_CONCLUSION_BYTES).toString('utf8').trim();
}

function createMaterializationPayload(conversationId: string, turns: readonly ChatTurn[]): DraftMaterializationPayload {
	return Object.freeze({ source: 'CHAT_DELIBERATION', conversationId, content: turns.map(turn => turn.conclusion).join('\n\n') });
}

function emptyConversation(): Conversation {
	return { turns: [], approvedSectionIds: new Set(), approvedBytes: 0 };
}

/** Composite key (design decision D): the open/terminated mode flag is scoped per (sessionIdentity, conversationId). */
function conversationKey(sessionIdentity: string, conversationId: string): string {
	return `${sessionIdentity}\0${conversationId}`;
}

/** Session-local tutor chat. It intentionally never reads or writes project state. */
export class ChatDeliberationService {
	private readonly conversations = new Map<string, Conversation>();
	/** Persisted per-(sessionIdentity,conversationId) chat-mode flag (design decision D / D1-D2). Cleared only by explicit CLOSE. */
	private readonly open = new Set<string>();
	/** Conversations that were explicitly closed or directly materialized (D5): reusing the same conversationId never resumes them. */
	private readonly terminated = new Set<string>();

	constructor(
		private readonly tutor: TutorAdapter | undefined,
		private readonly draftRegistry: PiSessionDraftRegistry,
		private readonly reviewer?: ReviewerAdapter,
		private readonly newConversationId: () => string = randomUUID,
	) {}

	latestConclusion(conversationId?: string): string | undefined {
		if (!conversationId) return undefined;
		return this.conversations.get(conversationId)?.turns.at(-1)?.conclusion;
	}

	currentManagedDocument(conversationId?: string): ChatDocumentContext | undefined {
		if (!conversationId) return undefined;
		return this.conversations.get(conversationId)?.document;
	}

	/** Routing consults this (design decision D1/D2) before allowing a keyword-inferred exit out of chat. */
	isOpen(sessionIdentity: string, conversationId: string): boolean {
		return this.open.has(conversationKey(sessionIdentity, conversationId));
	}

	/**
	 * Explicit CLOSE (task 2.2/2.7) and the sole exit for a direct materialization (D5).
	 * Discards ALL in-session accumulated state for this conversation -- it is never resumable afterward.
	 */
	close(sessionIdentity: string, conversationId: string): CloseDeliberationResult {
		const key = conversationKey(sessionIdentity, conversationId);
		const wasOpen = this.open.delete(key);
		this.conversations.delete(conversationId);
		this.draftRegistry.delete(sessionIdentity, conversationId);
		this.terminated.add(key);
		return { status: wasOpen ? 'closed' : 'not_open', conversationId };
	}

	async deliberate(input: { instruction: string; sessionIdentity: string; conversationId?: string; document?: ChatDocumentContext; guideFragments?: readonly ChatGuideFragment[] }): Promise<ChatDeliberationResult> {
		const conversationId = input.conversationId ?? `chat-${this.newConversationId()}`;
		const key = conversationKey(input.sessionIdentity, conversationId);
		if (this.terminated.has(key)) return this.blocked(conversationId, emptyConversation(), 'CONVERSATION_TERMINATED');
		const conversation = this.conversations.get(conversationId) ?? emptyConversation();
		if (!CHAT_CONVERSATION_ID.test(conversationId)) return this.blocked(conversationId, conversation, 'CHAT_CONVERSATION_ID_INVALID');
		if (!this.tutor) return this.blocked(conversationId, conversation, 'TUTOR_REQUIRED');
		this.open.add(key);
		const priorTurns = conversation.turns.slice(-MAX_CHAT_TURNS + 1);
		// Paper-guide reference context (task 3.5/3.6, spec I2): included ONLY on this conversation's first turn -- never reloaded on later turns, matching the preserved per-turn-bounded, no-reload design invariant.
		const context = this.context(conversationId, priorTurns, input.instruction, input.document, priorTurns.length === 0 ? input.guideFragments : undefined);
		try {
			let assessment = validateTutorAssessment(await modelCall('tutor', () => this.tutor!.assess({ instruction: input.instruction, context })), context.fragments.map((fragment) => fragment.entryId));
			let modelCalls = 1, tutorCalls = 1, reviewerCalls = 0, repairCycles = 0;
			let refuteOutcome: RefuteOutcome = 'NOT_RUN';
			if (this.reviewer && CONCRETE_CHANGE_DECISIONS.has(assessment.decision)) {
				while (true) {
					const review = validateReviewerAssessment(await modelCall('reviewer', () => this.reviewer!.review({ instruction: input.instruction, context, plan: { summary: assessment.summary, proposedAlternative: assessment.proposedAlternative } })));
					modelCalls += 1; reviewerCalls += 1;
					if (review.decision === 'APPROVE') { refuteOutcome = 'ACCEPT'; break; }
					if (review.decision === 'BLOCK') { refuteOutcome = 'REJECT'; break; }
					if (review.decision === 'NEEDS_CLARIFICATION') { refuteOutcome = 'NEEDS_CLARIFICATION'; break; }
					// APPROVE_WITH_CHANGES: repair, bounded to MAX_REPAIR_CYCLES (spec D3).
					if (repairCycles >= MAX_REPAIR_CYCLES) { refuteOutcome = 'REPAIR_EXHAUSTED'; break; }
					repairCycles += 1;
					const repairInstruction = `Repair the supplied proposal using this reviewer feedback: ${(review.requiredChanges.find((item) => item.trim().length > 0) ?? review.scientificCoherence)}`;
					assessment = validateTutorAssessment(await modelCall('tutor', () => this.tutor!.assess({ instruction: repairInstruction, context })), context.fragments.map((fragment) => fragment.entryId));
					modelCalls += 1; tutorCalls += 1;
				}
			}
			const conclusion = boundedConclusion(assessment.summary);
			if (!conclusion) return this.blocked(conversationId, conversation, 'TUTOR_CONCLUSION_INVALID', modelCalls);
			// Growth advisory accumulation (task 2.10): a concrete change only counts toward the pending approved set once the refute loop (when it ran) actually approved it.
			const concreteChangeApproved = CONCRETE_CHANGE_DECISIONS.has(assessment.decision) && (refuteOutcome === 'ACCEPT' || refuteOutcome === 'NOT_RUN');
			// Section identity for the growth advisory (re-audit cleanup): growth-threshold
			// semantics count INDEPENDENT (disjoint) approved section targets, not raw
			// approved turns, so repeated approvals to the SAME section must not each add 1.
			// `ChatDeliberationService` has no structural, byte-precise target resolver
			// (unlike orchestrator.ts's target-resolver) -- the closest per-approval
			// identifier available at this layer is the tutor's own declared
			// `TutorAssessment.affectedEntryIds` (already validated to be a subset of this
			// turn's context fragment entry ids). When the tutor declares one or more
			// affected entry ids, those ids ARE the section identity: a Set dedupes exact
			// repeats across turns (e.g. the same loaded document referenced again).
			// When the tutor declares none (the common case in existing fixtures/tests),
			// there is no signal to dedupe against, so fall back to one synthetic
			// per-turn identifier -- behaviorally identical to the pre-fix per-turn count
			// for that turn, and still correctly additive across turns that carry no signal.
			const turnSectionIds = concreteChangeApproved
				? (assessment.affectedEntryIds.length > 0 ? assessment.affectedEntryIds : [`turn:${conversation.turns.length}`])
				: [];
			const approvedSectionIds: ReadonlySet<string> = turnSectionIds.length ? new Set([...conversation.approvedSectionIds, ...turnSectionIds]) : conversation.approvedSectionIds;
			const approvedBytes = conversation.approvedBytes + (concreteChangeApproved ? Buffer.byteLength(assessment.proposedAlternative ?? assessment.summary) : 0);
			const updatedConversation: Conversation = { turns: [...priorTurns, { conclusion, assessment }], document: input.document ?? conversation.document, approvedSectionIds, approvedBytes };
			this.draftRegistry.put(input.sessionIdentity, conversationId, createMaterializationPayload(conversationId, updatedConversation.turns));
			this.remember(conversationId, updatedConversation);
			const documentBytes = updatedConversation.document?.bytesRead ?? 0;
			const growthAdvisory = evaluateSuccessorGrowthThreshold({ approvedSectionCount: approvedSectionIds.size, approvedBytes, documentBytes });
			return {
				status: 'deliberated', conversationId, conclusion, assessment,
				alternatives: assessment.proposedAlternative ? [assessment.proposedAlternative] : [], risks: [assessment.riskLevel], unresolvedQuestions: assessment.unresolvedQuestions,
				context: { turnCount: updatedConversation.turns.length, reusedConclusion: priorTurns.length > 0 }, modelCalls, tutorCalls, reviewerCalls, mutations: 0, receiptId: null,
				manifestStatus: 'NOT_PUBLISHED', auditStatus: 'NOT_RUN', selfAuditStatus: 'NOT_RUN', recoveryStatus: 'not_required', nextAction: assessment.unresolvedQuestions.length ? 'clarify_request' : null,
				refute: { ran: refuteOutcome !== 'NOT_RUN', outcome: refuteOutcome, repairCycles },
				growthAdvisory,
			};
		} catch (error) {
			return this.blocked(conversationId, conversation, error instanceof Error ? error.message : String(error), 1);
		}
	}

	private context(conversationId: string, turns: ChatTurn[], instruction: string, document?: ChatDocumentContext, guideFragments?: readonly ChatGuideFragment[]): LocalContext {
		let bytes = 0;
		const fragments = [
			...(guideFragments ?? []).map((guide, index) => ({ entryId: `paper-guide:${index}:${guide.path}`, type: 'document' as const, text: guide.content.slice(0, MAX_CHAT_GUIDE_CONTEXT_BYTES), textSha256: '', headingPath: ['Guide', guide.path] })),
			...(document ? [{ entryId: `chat-document:${document.filename}`, type: 'document' as const, text: document.content, textSha256: document.documentSha256, headingPath: ['Document', document.filename] }] : []),
			...turns.map((turn, index) => ({ entryId: `chat-turn-${index + 1}`, type: 'paragraph' as const, text: turn.conclusion, textSha256: '', headingPath: ['Conversation', conversationId] })),
		].filter((fragment) => {
			const size = Buffer.byteLength(fragment.text);
			if (bytes + size > MAX_CONTEXT_BYTES) return false;
			bytes += size;
			return true;
		});
		return { documentSha256: document?.documentSha256 ?? `chat:${conversationId}`, targetEntryId: fragments.at(-1)?.entryId ?? 'chat-turn-0', instruction, fragments, nearbySymbols: {}, directReferences: [], maxBytes: MAX_CONTEXT_BYTES };
	}

	private remember(conversationId: string, conversation: Conversation) {
		if (!this.conversations.has(conversationId) && this.conversations.size >= MAX_CHAT_CONVERSATIONS) this.conversations.delete(this.conversations.keys().next().value!);
		this.conversations.set(conversationId, conversation);
	}

	private blocked(conversationId: string, conversation: Pick<Conversation, 'turns'>, reason: string, modelCalls = 0): ChatDeliberationResult {
		return { status: 'blocked', conversationId, alternatives: [], risks: [], unresolvedQuestions: [], context: { turnCount: conversation.turns.length, reusedConclusion: conversation.turns.length > 0 }, modelCalls, tutorCalls: modelCalls, reviewerCalls: 0, mutations: 0, receiptId: null, manifestStatus: 'NOT_PUBLISHED', auditStatus: 'NOT_RUN', selfAuditStatus: 'NOT_RUN', recoveryStatus: 'not_required', nextAction: 'clarify_request', reason };
	}
}
