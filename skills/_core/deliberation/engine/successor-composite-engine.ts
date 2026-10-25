import { sha256, type DocumentState, type StructuralPatchSelector } from './types.js';
import {
	preflightSuccessorBlockPlan,
	type FrozenSuccessorSourceIdentity,
	type ResolvedSuccessorBlockTarget,
	type SuccessorBlock,
	type SuccessorBlockPlan,
} from './block-plan.js';

// Sequential composite successor engine.
//
// Consumes a frozen, preflight-ready SuccessorBlockPlan and the source
// DocumentState and deterministically builds ONE internal candidate document by
// applying each block's authorized replacement in execution order. It is pure:
// it reads no filesystem, mutates no DocumentState, and publishes nothing. It
// produces the composed candidate bytes plus a manifest; wiring this candidate
// into the single guarded publication path (one preview, one acceptance, one
// atomic successor) is a later cut.
//
// Invariants enforced here (the block plan's per-transition contract):
//  - the plan must be preflight-ready against the same source (hard gate);
//  - every block target is source-frozen and disjoint (merge groups, i.e.
//    overlapping targets, are explicitly deferred, never silently applied);
//  - each block's declared `candidateSha256` must equal the SHA-256 of the
//    running candidate document after that block is applied, in execution order;
//  - every byte outside the union of block spans is preserved byte-for-byte.

/** One block's authorized, resolved replacement against its source span. */
export type SuccessorBlockReplacement = Readonly<{
	blockId: string;
	entryId: string;
	startByte: number;
	endByte: number;
	replacementSha256: string;
	candidateSha256: string;
}>;

/** A contiguous source region preserved unchanged in the composed candidate. */
export type PreservedRegionEvidence = Readonly<{ startByte: number; endByte: number; sha256: string }>;

export type SuccessorCompositeManifest = Readonly<{
	source: FrozenSuccessorSourceIdentity;
	executionOrder: readonly string[];
	candidateSha256: string;
	unionStartByte: number;
	unionEndByte: number;
	blocks: readonly SuccessorBlockReplacement[];
	preservedRegions: readonly PreservedRegionEvidence[];
}>;

export type SuccessorCompositeDiagnostic = Readonly<{
	code:
		| 'BLOCK_PLAN_NOT_READY'
		| 'BLOCK_MERGE_GROUP_UNSUPPORTED'
		| 'BLOCK_REPLACEMENT_MISSING'
		| 'BLOCK_REPLACEMENT_INVALID'
		| 'BLOCK_CANDIDATE_HASH_MISMATCH'
		| 'COMPOSITE_NO_OP'
		| 'COMPOSITE_UNTOUCHED_INVARIANT';
	blockId?: string;
}>;

export type SuccessorCompositeResult =
	| Readonly<{ status: 'composed'; candidateBytes: Buffer; manifest: SuccessorCompositeManifest }>
	| Readonly<{ status: 'blocked'; diagnostics: readonly SuccessorCompositeDiagnostic[] }>;

/**
 * Resolves the authorized replacement text for one block against the running
 * candidate. For disjoint blocks the running document equals the source at the
 * block span, so `running` and `source` are the same document here. The
 * resolver is the injection point for the content-only successor planner in
 * production and for scripted responses in tests; it never receives authority
 * to choose targets, offsets, or additional actions.
 */
export type SuccessorBlockReplacementResolver = (input: {
	block: SuccessorBlock;
	entryId: string;
	source: DocumentState;
	running: DocumentState;
}) => string | Promise<string>;

function blocked(diagnostics: SuccessorCompositeDiagnostic[]): SuccessorCompositeResult {
	return { status: 'blocked', diagnostics };
}

/**
 * Splices disjoint, ascending, non-overlapping source spans in a single pass.
 *
 * Ordered by `(startByte, endByte)` ascending -- NOT `startByte` alone -- so a
 * zero-width `insert` point that shares its exact offset with the START of a
 * wider `replace`/`delete` span (a boundary-adjacent, non-overlapping pair,
 * e.g. an ADD placed immediately `before` an entry that is also deleted)
 * always sorts before that wider span. Without this secondary key, ties would
 * fall back to array order and could process the wider span first, which
 * advances the running cursor PAST the zero-width point and makes the
 * subsequent insert's `source.subarray(cursor, point)` slice invalid --
 * silently re-emitting already-consumed source bytes. Ascending `endByte`
 * cannot reorder two genuinely disjoint, non-tied spans (their `startByte`
 * values already differ), so this is a pure tie-break, not a semantic change.
 */
function spliceDisjoint(source: Buffer, edits: readonly { startByte: number; endByte: number; replacement: Buffer }[]): Buffer {
	const ordered = [...edits].sort((left, right) => left.startByte - right.startByte || left.endByte - right.endByte);
	const parts: Buffer[] = [];
	let cursor = 0;
	for (const edit of ordered) {
		parts.push(source.subarray(cursor, edit.startByte));
		parts.push(edit.replacement);
		cursor = edit.endByte;
	}
	parts.push(source.subarray(cursor));
	return Buffer.concat(parts);
}

/**
 * Builds the composed successor candidate from a frozen block plan.
 *
 * Returns `composed` with the candidate bytes and a per-block manifest, or
 * `blocked` with specific diagnostics. Never publishes and never mutates the
 * source.
 */
export async function composeSuccessorBlockCandidate(
	plan: SuccessorBlockPlan,
	source: DocumentState,
	resolve: SuccessorBlockReplacementResolver,
): Promise<SuccessorCompositeResult> {
	const preflight = preflightSuccessorBlockPlan(plan, source);
	if (preflight.status !== 'ready') return blocked([{ code: 'BLOCK_PLAN_NOT_READY' }]);

	const blocks = new Map(plan.blocks.map((block) => [block.id, block]));

	// Merge groups (overlapping source targets) require intermediate re-resolution
	// and are deferred to a later cut. Reject explicitly rather than silently
	// applying overlapping edits as if disjoint.
	if (plan.blocks.some((block) => block.mergeGroupId !== undefined)) {
		return blocked([{ code: 'BLOCK_MERGE_GROUP_UNSUPPORTED' }]);
	}

	const diagnostics: SuccessorCompositeDiagnostic[] = [];
	const replacements = new Map<string, { entryId: string; startByte: number; endByte: number; replacement: Buffer; replacementSha256: string }>();

	for (const blockId of preflight.executionOrder) {
		const block = blocks.get(blockId)!;
		const selector: StructuralPatchSelector = (block.target as ResolvedSuccessorBlockTarget).selector;
		const text = await resolve({ block, entryId: selector.entryId, source, running: source });
		if (text === undefined || text === null) {
			diagnostics.push({ code: 'BLOCK_REPLACEMENT_MISSING', blockId });
			continue;
		}
		// `delete`-kind blocks are the ONE case where an empty replacement is
		// authorized (removing a non-empty source span); every other kind
		// (`replace`, the default, and `insert`) still requires non-empty text,
		// unchanged. A `delete`-kind block declaring non-empty text is rejected
		// too -- it would silently behave like a hidden replace.
		const isDelete = block.op === 'delete';
		if (typeof text !== 'string' || (isDelete ? text.length !== 0 : text.length === 0)) {
			diagnostics.push({ code: 'BLOCK_REPLACEMENT_INVALID', blockId });
			continue;
		}
		const replacement = Buffer.from(text, 'utf8');
		replacements.set(blockId, {
			entryId: selector.entryId,
			startByte: selector.startByte,
			endByte: selector.endByte,
			replacement,
			replacementSha256: sha256(replacement),
		});
	}
	if (diagnostics.length) return blocked(diagnostics);

	// Verify the per-transition contract: after applying blocks[order[0..k]] at
	// their source spans, the running candidate hash must equal that block's
	// declared candidateSha256. Each intermediate is recomputed from source over
	// the ordered subset, which is well defined because the spans are disjoint.
	const manifestBlocks: SuccessorBlockReplacement[] = [];
	for (let k = 0; k < preflight.executionOrder.length; k++) {
		const subset = preflight.executionOrder.slice(0, k + 1).map((id) => replacements.get(id)!);
		const intermediate = spliceDisjoint(source.documentBytes, subset);
		const blockId = preflight.executionOrder[k];
		const block = blocks.get(blockId)!;
		if (sha256(intermediate) !== block.candidateSha256) {
			diagnostics.push({ code: 'BLOCK_CANDIDATE_HASH_MISMATCH', blockId });
			continue;
		}
		const current = replacements.get(blockId)!;
		manifestBlocks.push({
			blockId,
			entryId: current.entryId,
			startByte: current.startByte,
			endByte: current.endByte,
			replacementSha256: current.replacementSha256,
			candidateSha256: block.candidateSha256,
		});
	}
	if (diagnostics.length) return blocked(diagnostics);

	const allEdits = preflight.executionOrder.map((id) => replacements.get(id)!);
	const candidateBytes = spliceDisjoint(source.documentBytes, allEdits);
	const candidateSha256 = sha256(candidateBytes);

	if (candidateBytes.equals(source.documentBytes)) return blocked([{ code: 'COMPOSITE_NO_OP' }]);

	// Byte-preservation invariant: every region outside the union of block spans
	// must be identical to the source. Build the preserved regions from the gaps
	// between the ordered spans and verify them against the composed candidate.
	// Ordered by `(startByte, endByte)` ascending -- matching `spliceDisjoint`'s
	// own tie-break exactly -- so a zero-width `insert` point sharing its offset
	// with a wider span's own start walks in the SAME order it was actually
	// spliced in; a mismatched order here would misalign this loop's running
	// `sourceCursor`/`candidateCursor` against the real candidate bytes and
	// falsely reject (or falsely accept) the untouched-byte invariant.
	const spans = allEdits.map((edit) => ({ startByte: edit.startByte, endByte: edit.endByte, replacementLength: edit.replacement.length })).sort((left, right) => left.startByte - right.startByte || left.endByte - right.endByte);
	const preservedRegions: PreservedRegionEvidence[] = [];
	let sourceCursor = 0;
	let candidateCursor = 0;
	for (const span of spans) {
		const sourcePrefix = source.documentBytes.subarray(sourceCursor, span.startByte);
		const candidatePrefix = candidateBytes.subarray(candidateCursor, candidateCursor + sourcePrefix.length);
		if (!sourcePrefix.equals(candidatePrefix)) return blocked([{ code: 'COMPOSITE_UNTOUCHED_INVARIANT' }]);
		if (sourcePrefix.length > 0) preservedRegions.push({ startByte: sourceCursor, endByte: span.startByte, sha256: sha256(sourcePrefix) });
		sourceCursor = span.endByte;
		candidateCursor += sourcePrefix.length + span.replacementLength;
	}
	const sourceTail = source.documentBytes.subarray(sourceCursor);
	const candidateTail = candidateBytes.subarray(candidateCursor);
	if (!sourceTail.equals(candidateTail)) return blocked([{ code: 'COMPOSITE_UNTOUCHED_INVARIANT' }]);
	if (sourceTail.length > 0) preservedRegions.push({ startByte: sourceCursor, endByte: source.documentBytes.length, sha256: sha256(sourceTail) });

	const manifest: SuccessorCompositeManifest = {
		source: plan.source,
		executionOrder: preflight.executionOrder,
		candidateSha256,
		unionStartByte: spans[0].startByte,
		unionEndByte: spans[spans.length - 1].endByte,
		blocks: manifestBlocks,
		preservedRegions,
	};
	return { status: 'composed', candidateBytes, manifest };
}
