import type { CreateSuccessorPayloadV1, MaterializationClaimProvenance, RevisionEvidence } from './revision-domain.js';
import { sha256, type DocumentState, type EditAction, type EditPlan, type StructuralEntry } from './types.js';
import { materializeCompositeTarget, resolveSuccessorTarget } from './target-resolver.js';
import { DOMAIN } from './domain-profile.js';

function sameRevision(state: DocumentState, expected: RevisionEvidence) {
	return state.filename === expected.filename && state.revision === expected.revision && state.documentSha256 === expected.documentSha256;
}

function anchorFor(state: DocumentState, excludeEntryIds: ReadonlySet<string> = new Set()): StructuralEntry | undefined {
	return [...state.structuralIndex.entries]
		.filter((entry) => entry.endByte > entry.startByte && !excludeEntryIds.has(entry.entryId))
		.sort((left, right) => right.endByte - left.endByte || right.startByte - left.startByte || left.entryId.localeCompare(right.entryId))[0];
}

/** A structural claim's disjoint splice span (the byte range it occupies for overlap purposes) plus its compiled action. */
type StructuralClaim = { claim: MaterializationClaimProvenance; entry: StructuralEntry; startByte: number; endByte: number; action: EditAction };

/**
 * Resolves one claim's `proposedEdit` (when present) against the CURRENT base
 * -- an EXPLICIT document-index lookup, never fuzzy summary matching -- into
 * its anchor/target entry, disjoint splice span, and compiled `EditAction`.
 * Supports three of the five kinds `parseProposedEdit` recognizes: `replace`
 * (a non-empty span), `insert` (a zero-width point at the anchor's own start
 * or end boundary -- normalized to `before`/`after` only at capture time), and
 * `delete` (the target's full non-empty span, empty replacement). Returns
 * `undefined` on drift (missing entry, a `document`-type entry, or a
 * would-be-empty delete span) so the caller falls back to the pre-existing
 * summary-annotation route.
 *
 * `move`/`copy` (relocations) are a deliberate, disclosed scope decision for
 * this SECONDARY/filename-era route: it falls through to `undefined` (the
 * same pre-existing summary-annotation fallback) exactly like any other
 * unrecognized kind, unchanged. Splicing a relocation into this planner's
 * single combined plan would conflict with `patch-compiler.ts`'s own
 * `move`/`copy` compilation, which requires the plan to contain EXACTLY one
 * action and never mixes a relocation with other structural edits -- the
 * SEPARATE-VERSION grouping this slice implements for the PRIMARY
 * lifecycle-v1 route (`scientific-workflow-runtime.ts`) has no analog here
 * without a larger redesign of this planner's single-plan-per-materialization
 * shape. A relocation claim routed through this planner therefore still
 * safely materializes as a summary annotation, never silently dropped.
 */
function resolveStructuralClaim(base: DocumentState, claim: MaterializationClaimProvenance): StructuralClaim | undefined {
	const edit = claim.proposedEdit;
	if (!edit) return undefined;
	if (edit.kind === 'replace') {
		const entry = base.structuralIndex.byId[edit.targetEntryId];
		if (!entry || entry.type === 'document') return undefined;
		return { claim, entry, startByte: entry.startByte, endByte: entry.endByte, action: { kind: 'replace', targetEntryId: entry.entryId, replacementText: edit.replacementText } };
	}
	if (edit.kind === 'insert') {
		const entry = base.structuralIndex.byId[edit.anchorEntryId];
		if (!entry || entry.type === 'document') return undefined;
		const point = edit.position === 'before' || edit.position === 'inside_start' ? entry.startByte : entry.endByte;
		return { claim, entry, startByte: point, endByte: point, action: { kind: 'insert', anchorEntryId: entry.entryId, position: edit.position, content: edit.content } };
	}
	if (edit.kind === 'delete') {
		const entry = base.structuralIndex.byId[edit.targetEntryId];
		if (!entry || entry.type === 'document' || entry.startByte >= entry.endByte) return undefined;
		return { claim, entry, startByte: entry.startByte, endByte: entry.endByte, action: { kind: 'delete', targetEntryId: entry.entryId, instructionEvidence: edit.instructionEvidence, reason: edit.reason } };
	}
	return undefined;
}

/**
 * Structural (real, byte-preserving) claims: those whose accepted decision
 * carries a `proposedEdit` resolved against the CURRENT base. Overlapping/
 * duplicate loci are never silently applied: both members of a colliding pair
 * degrade to the summary-annotation fallback instead of forcing an offset. A
 * zero-width `insert` point exactly at another claim's span boundary is NOT
 * an overlap (boundary-adjacent); strictly inside another span is.
 */
function resolveStructuralClaims(base: DocumentState, acceptedDecisions: readonly MaterializationClaimProvenance[]): { structural: StructuralClaim[]; fallback: MaterializationClaimProvenance[] } {
	const candidates = acceptedDecisions
		.map((claim) => resolveStructuralClaim(base, claim))
		.filter((item): item is StructuralClaim => !!item);
	const overlapping = new Set<string>();
	for (const left of candidates) for (const right of candidates) {
		if (left.claim.decisionId === right.claim.decisionId) continue;
		if (left.startByte < right.endByte && right.startByte < left.endByte) { overlapping.add(left.claim.decisionId); overlapping.add(right.claim.decisionId); }
	}
	const structural = candidates.filter((item) => !overlapping.has(item.claim.decisionId));
	const structuralIds = new Set(structural.map((item) => item.claim.decisionId));
	return { structural, fallback: acceptedDecisions.filter((claim) => !structuralIds.has(claim.decisionId)) };
}

/**
 * Resolves a single accepted decision's summary to its addressable heading/section
 * locus via `resolveSuccessorTarget` (the same resolver used elsewhere for
 * successor targets). Only attempted for exactly one accepted decision with
 * exactly one unambiguous candidate; anything else (zero, multiple decisions, or
 * an ambiguous/unresolved locus) intentionally returns `undefined` so the caller
 * falls back to the document-tail anchor unchanged.
 */
function resolveLocusAnchor(state: DocumentState, acceptedDecisions: readonly MaterializationClaimProvenance[]): StructuralEntry | undefined {
	if (acceptedDecisions.length !== 1) return undefined;
	const resolution = resolveSuccessorTarget(state, acceptedDecisions[0]!.summary);
	if (resolution.candidates.length !== 1) return undefined;
	return materializeCompositeTarget(state, resolution.candidates[0]!);
}

function validClaims(claims: readonly MaterializationClaimProvenance[]) {
	return claims.length > 0 && claims.every((claim, index) => typeof claim.summary === 'string' && claim.summary.trim().length > 0
		&& (index === 0 || claims[index - 1]!.decisionId < claim.decisionId));
}

function tailBlockContent(decisions: readonly MaterializationClaimProvenance[]): string {
	// Finding L6: was a hardcoded `'## Accepted scientific decisions'`, undeclared by any
	// profile. `DOMAIN.artifact.acceptedDecisionsHeading` defaults to the exact prior
	// literal when undeclared, so this is zero migration for either shipped host.
	const heading = DOMAIN.artifact.acceptedDecisionsHeading ?? 'Accepted scientific decisions';
	return [
		'',
		'',
		`## ${heading}`,
		'',
		...decisions.flatMap((claim) => [`### ${claim.decisionId}`, '', claim.summary.trim(), '']),
	].join('\n');
}

function instructionHashFor(acceptedDecisions: readonly MaterializationClaimProvenance[]): string {
	return sha256(JSON.stringify({ operation: 'CREATE_SUCCESSOR', decisionIds: acceptedDecisions.map((claim) => claim.decisionId) }));
}

/** Produces canonical V2 edit plans from a supplied frozen base and accepted decisions only. */
export class SuccessorEditPlanner {
	plan(input: { base: DocumentState; expectedRevision: RevisionEvidence; acceptedDecisions: readonly MaterializationClaimProvenance[] }): CreateSuccessorPayloadV1 {
		if (!sameRevision(input.base, input.expectedRevision) || !validClaims(input.acceptedDecisions)) throw new Error('MATERIALIZATION_SUCCESSOR_INPUT_INVALID');
		const { structural, fallback } = resolveStructuralClaims(input.base, input.acceptedDecisions);

		if (structural.length === 0) {
			// Unchanged pre-existing behavior: exactly the prior single-locus scoped
			// note, or the document-tail summary block -- no claim in this batch
			// carries a usable, resolvable structural edit.
			const locusAnchor = resolveLocusAnchor(input.base, input.acceptedDecisions);
			const anchor = locusAnchor ?? anchorFor(input.base);
			if (!anchor) throw new Error('MATERIALIZATION_SUCCESSOR_ANCHOR_MISSING');
			const content = locusAnchor
				? `\n\n> Accepted revision: ${input.acceptedDecisions[0]!.summary.trim()}\n`
				: tailBlockContent(input.acceptedDecisions);
			return this.buildPayload(input, [anchor.entryId], [{ kind: 'insert', anchorEntryId: anchor.entryId, position: 'after', content }], anchor);
		}

		// At least one decision carries a real, resolvable structural edit: apply
		// every resolvable structural edit (replace/insert/delete) directly at its
		// own locus -- ALL spliced into the SAME successor version, never a
		// separate one per decision -- and fold every remaining (no-proposedEdit,
		// or drifted/overlapping) decision into ONE shared document-tail summary
		// block, so no decision is ever silently lost.
		const structuralActions: EditAction[] = structural.map(({ action }) => action);
		const resolvedTargets = structural.map(({ entry }) => entry.entryId);
		const destructiveIntent = structuralActions.some((action) => action.kind === 'delete');
		const primaryAnchor = structural[0]!.entry;
		if (fallback.length === 0) return this.buildPayload(input, resolvedTargets, structuralActions, primaryAnchor, destructiveIntent);

		const tailAnchor = anchorFor(input.base, new Set(resolvedTargets)) ?? primaryAnchor;
		const actions: EditAction[] = [...structuralActions, { kind: 'insert', anchorEntryId: tailAnchor.entryId, position: 'after', content: tailBlockContent(fallback) }];
		return this.buildPayload(input, [...resolvedTargets, tailAnchor.entryId], actions, primaryAnchor, destructiveIntent);
	}

	private buildPayload(input: { base: DocumentState; expectedRevision: RevisionEvidence; acceptedDecisions: readonly MaterializationClaimProvenance[] }, resolvedTargets: string[], actions: EditAction[], anchor: StructuralEntry, destructiveIntent = false): CreateSuccessorPayloadV1 {
		const plan: EditPlan = {
			planVersion: '2' as const,
			documentSha256: input.base.documentSha256,
			intent: 'INSERT' as const,
			instructionHash: instructionHashFor(input.acceptedDecisions),
			resolvedTargets,
			semanticChange: false,
			destructiveIntent,
			cleanupLevel: 'NONE' as const,
			constraints: ['frozen-scientific-materialization'],
			actions,
			expectedEffects: ['apply accepted scientific decisions'],
			unresolvedQuestions: [],
		};
		return {
			kind: 'CREATE_SUCCESSOR',
			payloadVersion: 1,
			expectedBase: structuredClone(input.expectedRevision),
			patches: [{
				order: 1,
				plan,
				preconditions: {
					expectedRevision: structuredClone(input.expectedRevision),
					baseDocumentSha256: input.base.documentSha256,
					anchorEntryId: anchor.entryId,
					anchorTextSha256: anchor.textSha256,
				},
			}],
		};
	}
}
