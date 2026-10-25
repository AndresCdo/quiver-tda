import { sha256, type DocumentState, type StructuralPatchSelector } from './types.js';
import type { RevisionEvidence } from './revision-domain.js';

const BLOCK_ID = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/;
const SHA256 = /^[a-f0-9]{64}$/;

export type FrozenSuccessorSourceIdentity = Pick<RevisionEvidence, 'filename' | 'revision' | 'documentSha256'>;
export type ResolvedSuccessorBlockTarget = Readonly<{ status: 'resolved'; selector: StructuralPatchSelector }>;
export type UnresolvedSuccessorBlockTarget = Readonly<{ status: 'unresolved'; query?: string }>;
export type AmbiguousSuccessorBlockTarget = Readonly<{ status: 'ambiguous'; candidateEntryIds: readonly string[] }>;
export type SuccessorBlockTarget = ResolvedSuccessorBlockTarget | UnresolvedSuccessorBlockTarget | AmbiguousSuccessorBlockTarget;

/**
 * The block's splice kind. Absent (or `'replace'`) is the pre-existing,
 * backward-compatible shape: a non-empty source span replaced by non-empty
 * text. `'insert'` targets a zero-width source span (see `targetMatchesState`)
 * with non-empty content; `'delete'` targets a non-empty source span with
 * empty replacement text (see `successor-composite-engine.ts`).
 */
export type SuccessorBlockOp = 'replace' | 'insert' | 'delete';

export type SuccessorBlock = Readonly<{
	id: string;
	dependsOn: readonly string[];
	target: SuccessorBlockTarget;
	candidateSha256: string;
	mergeGroupId?: string;
	/** Defaults to `'replace'` when absent -- fully backward compatible. */
	op?: SuccessorBlockOp;
}>;

export type SuccessorBlockMergeGroup = Readonly<{
	id: string;
	blockIds: readonly string[];
	compatibility: 'OVERLAPPING_TARGETS';
}>;

/** Frozen, pure input for a future single-successor publication. This contract has no planner, executor, or publication authority. */
export type SuccessorBlockPlan = Readonly<{
	source: FrozenSuccessorSourceIdentity;
	orderedBlockIds: readonly string[];
	blocks: readonly SuccessorBlock[];
	mergeGroups: readonly SuccessorBlockMergeGroup[];
}>;

export type SuccessorBlockPlanDiagnostic = Readonly<{
	code:
		| 'BLOCK_ID_INVALID'
		| 'BLOCK_ID_DUPLICATE'
		| 'BLOCK_ORDER_INVALID'
		| 'BLOCK_DEPENDENCY_UNKNOWN'
		| 'BLOCK_DEPENDENCY_ORDER'
		| 'BLOCK_DEPENDENCY_CYCLE'
		| 'BLOCK_TARGET_UNRESOLVED'
		| 'BLOCK_TARGET_AMBIGUOUS'
		| 'BLOCK_TARGET_INVALID'
		| 'BLOCK_TARGET_STALE'
		| 'BLOCK_TARGET_OVERLAP'
		| 'BLOCK_INSERT_ORDER_AMBIGUOUS'
		| 'BLOCK_MERGE_GROUP_INVALID'
		| 'BLOCK_CANDIDATE_HASH_INVALID'
		| 'BLOCK_SOURCE_STALE';
	blockId?: string;
	dependencyId?: string;
	relatedBlockId?: string;
}>;

export type SuccessorBlockPlanPreflight =
	| Readonly<{ status: 'ready'; executionOrder: string[]; diagnostics: [] }>
	| Readonly<{ status: 'blocked'; diagnostics: SuccessorBlockPlanDiagnostic[] }>;

function stableStringCompare(left: string, right: string) {
	return left === right ? 0 : left < right ? -1 : 1;
}

function diagnosticOrder(left: SuccessorBlockPlanDiagnostic, right: SuccessorBlockPlanDiagnostic) {
	return stableStringCompare(left.code, right.code)
		|| stableStringCompare(left.blockId ?? '', right.blockId ?? '')
		|| stableStringCompare(left.dependencyId ?? '', right.dependencyId ?? '')
		|| stableStringCompare(left.relatedBlockId ?? '', right.relatedBlockId ?? '');
}

function sameSource(source: FrozenSuccessorSourceIdentity, state: DocumentState) {
	return source.filename === state.filename
		&& source.revision === state.revision
		&& source.documentSha256 === state.documentSha256
		&& source.documentSha256 === sha256(state.documentBytes);
}

function isResolvedSuccessorBlockTarget(target: unknown): target is ResolvedSuccessorBlockTarget {
	if (typeof target !== 'object' || !target) return false;
	const candidate = target as { status?: unknown; selector?: unknown };
	if (candidate.status !== 'resolved' || typeof candidate.selector !== 'object' || !candidate.selector) return false;
	const selector = candidate.selector as Partial<StructuralPatchSelector>;
	return typeof selector.entryId === 'string'
		&& typeof selector.startByte === 'number'
		&& typeof selector.endByte === 'number'
		&& typeof selector.textSha256 === 'string'
		&& typeof selector.documentSha256 === 'string';
}

const EMPTY_SHA256 = sha256(Buffer.alloc(0));

/**
 * Resolved-target staleness check, generalized for zero-width insertion
 * points: when `selector.startByte === selector.endByte` (an `insert`-kind
 * block's anchor splice point), the target is fresh iff the anchor entry
 * still exists at the expected document identity AND the zero-width point
 * still sits at one of that entry's own boundaries (its start, for a
 * `before`/`inside_start` insert, or its end, for an `after`/`inside_end`
 * insert). Otherwise (the pre-existing `replace`/`delete` shape) the full
 * entry span and its content hash must match exactly, unchanged.
 */
function targetMatchesState(target: ResolvedSuccessorBlockTarget, state: DocumentState) {
	const selector = target.selector;
	if (selector.documentSha256 !== state.documentSha256) return false;
	const entry = state.structuralIndex.byId[selector.entryId];
	if (!entry) return false;
	if (selector.startByte === selector.endByte) {
		return selector.textSha256 === EMPTY_SHA256
			&& (selector.startByte === entry.startByte || selector.startByte === entry.endByte);
	}
	return selector.startByte === entry.startByte
		&& selector.endByte === entry.endByte
		&& selector.textSha256 === entry.textSha256
		&& sha256(state.documentBytes.subarray(selector.startByte, selector.endByte)) === selector.textSha256;
}

function cyclicBlockIds(order: readonly string[], blocks: ReadonlyMap<string, SuccessorBlock>) {
	const active = new Set<string>();
	const visited = new Set<string>();
	const cyclic = new Set<string>();
	const visit = (id: string, trail: string[]) => {
		if (active.has(id)) {
			const cycleStart = trail.indexOf(id);
			for (const cycleId of trail.slice(cycleStart)) cyclic.add(cycleId);
			return;
		}
		if (visited.has(id)) return;
		visited.add(id);
		active.add(id);
		const block = blocks.get(id);
		for (const dependencyId of block?.dependsOn ?? []) if (blocks.has(dependencyId)) visit(dependencyId, [...trail, id]);
		active.delete(id);
	};
	for (const id of [...new Set([...order, ...blocks.keys()])].sort(stableStringCompare)) visit(id, []);
	return cyclic;
}

function compatibleMergeGroups(groups: readonly SuccessorBlockMergeGroup[], blocks: ReadonlyMap<string, SuccessorBlock>, diagnostics: SuccessorBlockPlanDiagnostic[]) {
	const compatible = new Map<string, ReadonlySet<string>>();
	for (const group of [...groups].sort((left, right) => stableStringCompare(left.id, right.id))) {
		const memberIds = new Set(group.blockIds);
		if (!BLOCK_ID.test(group.id) || memberIds.size !== group.blockIds.length || group.blockIds.length < 2 || group.compatibility !== 'OVERLAPPING_TARGETS' || [...memberIds].some((id) => !blocks.has(id))) {
			diagnostics.push({ code: 'BLOCK_MERGE_GROUP_INVALID' });
			continue;
		}
		if (compatible.has(group.id)) {
			diagnostics.push({ code: 'BLOCK_MERGE_GROUP_INVALID' });
			continue;
		}
		compatible.set(group.id, memberIds);
	}
	for (const block of blocks.values()) {
		if (block.mergeGroupId && !compatible.get(block.mergeGroupId)?.has(block.id)) diagnostics.push({ code: 'BLOCK_MERGE_GROUP_INVALID', blockId: block.id });
	}
	return compatible;
}

/** Validates frozen source/target identities and deterministic multi-block ordering without executing candidates or publishing output. */
export function preflightSuccessorBlockPlan(plan: SuccessorBlockPlan, source: DocumentState): SuccessorBlockPlanPreflight {
	if (!sameSource(plan.source, source)) return { status: 'blocked', diagnostics: [{ code: 'BLOCK_SOURCE_STALE' }] };
	const diagnostics: SuccessorBlockPlanDiagnostic[] = [];
	const blocks = new Map<string, SuccessorBlock>();
	for (const block of plan.blocks) {
		if (!BLOCK_ID.test(block.id)) diagnostics.push({ code: 'BLOCK_ID_INVALID', blockId: block.id });
		if (blocks.has(block.id)) diagnostics.push({ code: 'BLOCK_ID_DUPLICATE', blockId: block.id });
		else blocks.set(block.id, block);
		if (!SHA256.test(block.candidateSha256)) diagnostics.push({ code: 'BLOCK_CANDIDATE_HASH_INVALID', blockId: block.id });
	}
	const order = [...plan.orderedBlockIds];
	const orderSet = new Set(order);
	if (order.length !== orderSet.size || order.length !== blocks.size || order.some((id) => !BLOCK_ID.test(id) || !blocks.has(id)) || [...blocks.keys()].some((id) => !orderSet.has(id))) diagnostics.push({ code: 'BLOCK_ORDER_INVALID' });
	const position = new Map(order.map((id, index) => [id, index]));
	for (const id of [...blocks.keys()].sort(stableStringCompare)) {
		const block = blocks.get(id)!;
		for (const dependencyId of [...block.dependsOn].sort(stableStringCompare)) {
			if (!blocks.has(dependencyId)) diagnostics.push({ code: 'BLOCK_DEPENDENCY_UNKNOWN', blockId: id, dependencyId });
			else if ((position.get(dependencyId) ?? Infinity) >= (position.get(id) ?? -1)) diagnostics.push({ code: 'BLOCK_DEPENDENCY_ORDER', blockId: id, dependencyId });
		}
		const targetStatus = typeof block.target === 'object' && block.target ? (block.target as { status?: unknown }).status : undefined;
		if (targetStatus === 'unresolved') diagnostics.push({ code: 'BLOCK_TARGET_UNRESOLVED', blockId: id });
		else if (targetStatus === 'ambiguous') diagnostics.push({ code: 'BLOCK_TARGET_AMBIGUOUS', blockId: id });
		else if (!isResolvedSuccessorBlockTarget(block.target)) diagnostics.push({ code: 'BLOCK_TARGET_INVALID', blockId: id });
		else if (!targetMatchesState(block.target, source)) diagnostics.push({ code: 'BLOCK_TARGET_STALE', blockId: id });
	}
	for (const id of [...cyclicBlockIds(order, blocks)].sort(stableStringCompare)) diagnostics.push({ code: 'BLOCK_DEPENDENCY_CYCLE', blockId: id });
	const mergeGroups = compatibleMergeGroups(plan.mergeGroups, blocks, diagnostics);
	const resolved = order.map((id) => blocks.get(id)).filter((block): block is SuccessorBlock & { target: ResolvedSuccessorBlockTarget } => !!block && isResolvedSuccessorBlockTarget(block.target));
	for (let index = 0; index < resolved.length; index++) {
		const left = resolved[index]!;
		const leftTarget = left.target as ResolvedSuccessorBlockTarget;
		for (const right of resolved.slice(index + 1)) {
			const rightTarget = right.target as ResolvedSuccessorBlockTarget;
			const overlaps = leftTarget.selector.startByte < rightTarget.selector.endByte && rightTarget.selector.startByte < leftTarget.selector.endByte;
			const members = left.mergeGroupId && left.mergeGroupId === right.mergeGroupId ? mergeGroups.get(left.mergeGroupId) : undefined;
			if (overlaps && (!members || !members.has(left.id) || !members.has(right.id))) diagnostics.push({ code: 'BLOCK_TARGET_OVERLAP', blockId: right.id, relatedBlockId: left.id });
			// Two zero-width insert points sharing the EXACT same offset are not caught
			// by the strict-inequality overlap formula above (it requires each span to
			// extend past the other's start, which two equal zero-width points never
			// do). Without an explicit `dependsOn` relationship declaring which one
			// splices first, their relative order would otherwise depend on array
			// position alone -- a silent, unreviewable choice. Require an explicit
			// order; reject as ambiguous when neither declares one.
			const leftZeroWidth = leftTarget.selector.startByte === leftTarget.selector.endByte;
			const rightZeroWidth = rightTarget.selector.startByte === rightTarget.selector.endByte;
			const sameZeroWidthPoint = leftZeroWidth && rightZeroWidth && leftTarget.selector.startByte === rightTarget.selector.startByte;
			if (sameZeroWidthPoint && !left.dependsOn.includes(right.id) && !right.dependsOn.includes(left.id)) diagnostics.push({ code: 'BLOCK_INSERT_ORDER_AMBIGUOUS', blockId: right.id, relatedBlockId: left.id });
		}
	}
	const canonicalDiagnostics = diagnostics.sort(diagnosticOrder);
	return canonicalDiagnostics.length ? { status: 'blocked', diagnostics: canonicalDiagnostics } : { status: 'ready', executionOrder: order, diagnostics: [] };
}
