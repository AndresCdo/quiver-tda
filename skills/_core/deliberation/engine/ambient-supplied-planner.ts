import type { DocumentState, EditAction, SemanticEditPlanner, SemanticPlannerInput, TargetCandidate } from './types.js';
import { parseProposedEdit, sha256 } from './types.js';

// Ambient-supplied planner (design `sdd/proposal-deliberation-ambient-model`, SLICE 1).
//
// A thin echo-and-VALIDATE `SemanticEditPlanner`: it makes NO model/network call.
// It plugs into the exact same injectable seam the tests already use to script
// `SemanticEditPlanner.plan()` (see `orchestrator.ts`'s `semanticPlanner`
// parameter) and the exact seam `production-planner-adapter.ts` occupied in
// production. Instead of asking a separate model, it returns decisions the
// AMBIENT model (the caller -- e.g. the conversational agent driving
// `proposal_deliberation_execute`) already deliberated and resolved in-conversation.
//
// The ambient model can still err -- name the wrong section, alter text it
// was not authorized to alter, or send a malformed action -- so this module
// carries the SAME planner OUTPUT validation `production-planner-adapter.ts`
// enforced on a real model response (`WRONG_TARGET_ENTRY_ID`,
// `ALTERED_REPLACEMENT_TEXT`, malformed action shape, unexpected keys, wrong
// action count), re-aimed at the caller-supplied `resolvedDecisions` instead of
// a model's structured-output response. Nothing here is dropped or weakened.

export type AmbientPlannerDiagnosticCode =
	| 'MALFORMED_DECISION_SHAPE'
	| 'UNEXPECTED_DECISION_FIELD'
	| 'WRONG_ACTION_KIND'
	| 'WRONG_TARGET_ENTRY_ID'
	| 'ALTERED_REPLACEMENT_TEXT'
	| 'NO_MATCHING_DECISION'
	| 'AMBIGUOUS_MATCHING_DECISIONS';

export type AmbientPlannerDiagnosticStage = 'adapter';

/**
 * Mirrors `production-planner-adapter.ts`'s `ProductionPlannerResponseError`
 * shape exactly (`code`, `diagnostic.{code,stage}`, `invocation.{modelCalls,
 * plannerCalls}`) so `edit-planner.ts`'s existing, untouched
 * `plannerInvocationDiagnostic` fail-closed detection recognizes this error
 * the same way it recognizes a rejected model response, without any change to
 * that core (STAY) module. `invocation.{modelCalls,plannerCalls}` describes the
 * SHAPE `edit-planner.ts` expects to see on a rejected planner invocation --
 * it does not assert a real network call happened (none does, on this path).
 */
export class AmbientPlannerResponseError extends Error {
	readonly code = 'PRODUCTION_PLANNER_RESPONSE_REJECTED' as const;
	readonly diagnostic: Readonly<{ code: AmbientPlannerDiagnosticCode; stage: AmbientPlannerDiagnosticStage }>;
	readonly invocation = Object.freeze({ modelCalls: 1, plannerCalls: 1 });

	constructor(diagnosticCode: AmbientPlannerDiagnosticCode) {
		super(`PRODUCTION_PLANNER_RESPONSE_REJECTED:${diagnosticCode}`);
		this.name = 'AmbientPlannerResponseError';
		this.diagnostic = Object.freeze({ code: diagnosticCode, stage: 'adapter' as const });
	}
}

const REPLACE_KEYS = new Set(['kind', 'targetEntryId', 'replacementText', 'semanticChange', 'rationale']);
const INSERT_KEYS = new Set(['kind', 'anchorEntryId', 'position', 'content']);
const DELETE_KEYS = new Set(['kind', 'targetEntryId', 'instructionEvidence', 'reason']);
const MOVE_COPY_KEYS = new Set(['kind', 'sourceEntryIds', 'destinationAnchorId', 'position', 'moveMode', 'removeSource', 'cleanupLevel', 'transformedContent']);

function isRecord(value: unknown): value is Record<string, unknown> {
	return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function unexpectedKeys(value: Record<string, unknown>, allowed: ReadonlySet<string>): string[] {
	return Object.keys(value).filter((key) => !allowed.has(key));
}

function allowedKeysFor(kind: unknown): ReadonlySet<string> | undefined {
	if (kind === 'replace') return REPLACE_KEYS;
	if (kind === 'insert') return INSERT_KEYS;
	if (kind === 'delete') return DELETE_KEYS;
	if (kind === 'move' || kind === 'copy') return MOVE_COPY_KEYS;
	return undefined;
}

/** The entryId a decision names as its own locus -- `replace`/`delete` via `targetEntryId`, `insert` via `anchorEntryId`, `move`/`copy` via its own `sourceEntryIds[0]` (matched only so a wrongly-shaped relocation decision fails closed with `WRONG_ACTION_KIND`, never silently ignored as unmatched). */
function decisionTargetEntryId(decision: Record<string, unknown>): string | undefined {
	if (typeof decision.targetEntryId === 'string') return decision.targetEntryId;
	if (typeof decision.anchorEntryId === 'string') return decision.anchorEntryId;
	if (Array.isArray(decision.sourceEntryIds) && typeof decision.sourceEntryIds[0] === 'string') return decision.sourceEntryIds[0];
	return undefined;
}

/**
 * Builds a `SemanticEditPlanner` over a caller-supplied, already-resolved
 * decision batch. Every `plan()` call is independent and pure: it looks up,
 * from the FULL batch, the ONE decision whose own target matches
 * `input.target.entryId` -- the engine-resolved locus for THIS call -- so the
 * same planner instance is safely reusable across a multi-section
 * `CREATE_SUCCESSOR` request (one `plan()` call per independent resolved
 * target, exactly like the model-backed path).
 *
 * Only `kind:'replace'` decisions can ever complete a `CREATE_SUCCESSOR`
 * request: `edit-planner.ts`'s `buildEditPlan` (STAY, untouched by this
 * slice) already hard-requires the returned plan to carry exactly one
 * `replace` action for a MODIFY-intent successor. A `insert`/`delete`/
 * `move`/`copy` decision is still SHAPE-validated here (so a malformed one is
 * never silently ignored), but is rejected with `WRONG_ACTION_KIND` before it
 * can reach that downstream invariant.
 */
export function createAmbientSuppliedPlanner(decisions: readonly EditAction[]): SemanticEditPlanner {
	return {
		async plan(input: SemanticPlannerInput) {
			const targetEntryId = input.target?.entryId;
			if (!targetEntryId) throw new AmbientPlannerResponseError('NO_MATCHING_DECISION');

			const rawCandidates = decisions.filter(isRecord);
			const matching = rawCandidates.filter((decision) => decisionTargetEntryId(decision) === targetEntryId);
			if (matching.length === 0) {
				const anyBound = rawCandidates.some((decision) => decisionTargetEntryId(decision) !== undefined);
				throw new AmbientPlannerResponseError(anyBound ? 'WRONG_TARGET_ENTRY_ID' : 'NO_MATCHING_DECISION');
			}
			if (matching.length > 1) throw new AmbientPlannerResponseError('AMBIGUOUS_MATCHING_DECISIONS');

			const raw = matching[0];
			const allowed = allowedKeysFor(raw.kind);
			if (!allowed) throw new AmbientPlannerResponseError('MALFORMED_DECISION_SHAPE');
			if (unexpectedKeys(raw, allowed).length > 0) throw new AmbientPlannerResponseError('UNEXPECTED_DECISION_FIELD');

			const parsed = parseProposedEdit(raw);
			if (!parsed) throw new AmbientPlannerResponseError('MALFORMED_DECISION_SHAPE');

			if (parsed.kind !== 'replace') throw new AmbientPlannerResponseError('WRONG_ACTION_KIND');
			if (parsed.targetEntryId !== targetEntryId) throw new AmbientPlannerResponseError('WRONG_TARGET_ENTRY_ID');
			if (input.fidelity?.replacementBlock !== undefined && parsed.replacementText !== input.fidelity.replacementBlock) {
				throw new AmbientPlannerResponseError('ALTERED_REPLACEMENT_TEXT');
			}

			return {
				actions: [{ kind: 'replace', targetEntryId: parsed.targetEntryId, replacementText: parsed.replacementText }],
				unresolvedQuestions: [],
			};
		},
	};
}

// Ambient composite decision reduction (design `sdd/proposal-deliberation-ambient-model`,
// SLICE 1b). `createAmbientSuppliedPlanner` above stays REPLACE-only forever --
// `edit-planner.ts`'s `buildEditPlan` hard-requires exactly one `replace` action
// for a MODIFY-intent successor (STAY, untouched). The functions below give
// CREATE_SUCCESSOR + `resolvedDecisions` a SECOND, parallel route that bypasses
// `buildEditPlan` entirely for `insert`/`delete`/`move`/`copy` (and `replace`)
// decisions, reducing them into the SAME disjoint, byte-preserving splice parts
// `scientific-workflow-runtime.ts`'s `resolveStructuralClaim` already produces
// for the deliberation/materialization route -- reusing the identical
// `composeSuccessorBlockCandidate` machinery (via `patch-compiler.ts`'s
// `compileSuccessorCompositeChangeset`) instead of a second byte-exact engine.

/** One disjoint splice part -- mirrors `scientific-workflow-runtime.ts`'s `resolveStructuralClaim` part shape exactly, plus the insert boundary (`before`/`after`) `patch-compiler.ts` needs to build a `CompiledPatch`. */
export type AmbientCompositePart = Readonly<{
	entryId: string;
	startByte: number;
	endByte: number;
	textSha256: string;
	replacementText: string;
	op: 'replace' | 'insert' | 'delete';
	position?: 'before' | 'after';
}>;

/** One homogeneous group (either every decision in-place, or every decision a relocation) of resolved decisions, bound to the ORIGINAL resolved `targets` array by index -- `targetIndices` lets a mixed batch re-resolve just the relocation half's ORIGINAL locus queries after the in-place half publishes (see `orchestrator.ts`'s `acceptAmbientCompositeSuccessor`). */
export type AmbientCompositeGroup = Readonly<{
	targetIndices: readonly number[];
	targetIds: readonly string[];
	parts: readonly AmbientCompositePart[];
	actions: readonly EditAction[];
}>;

export type AmbientCompositeResolution = Readonly<{
	inPlace: AmbientCompositeGroup;
	relocation: AmbientCompositeGroup;
}>;

const EMPTY_TEXT_SHA256 = sha256(Buffer.alloc(0));

function declaredEntryIds(parsed: EditAction): readonly string[] {
	if (parsed.kind === 'replace' || parsed.kind === 'delete') return [parsed.targetEntryId];
	if (parsed.kind === 'insert') return [parsed.anchorEntryId];
	if (parsed.kind === 'move' || parsed.kind === 'copy') return [parsed.sourceEntryIds[0]!, parsed.destinationAnchorId];
	return [];
}

/**
 * Validates and reduces a caller-supplied `resolvedDecisions` batch of ANY
 * `EditAction` kind against the engine-resolved `targets` (design contract:
 * every decision's own declared entryId(s) -- `targetEntryId`/`anchorEntryId`
 * for `replace`/`delete`/`insert`, `sourceEntryIds[0]`+`destinationAnchorId`
 * for `move`/`copy` -- must name a locus the engine itself already resolved,
 * exactly like the replace-only planner above). Carries the SAME OUTPUT
 * VALIDATION (`MALFORMED_DECISION_SHAPE`, `UNEXPECTED_DECISION_FIELD`,
 * `WRONG_TARGET_ENTRY_ID`, `NO_MATCHING_DECISION`, `AMBIGUOUS_MATCHING_DECISIONS`)
 * generalized from ONE resolved target to the WHOLE resolved set: every
 * resolved target must be claimed by EXACTLY one decision (a `move`/`copy`
 * decision claims two -- its source AND its destination).
 *
 * Structural drift (missing entry, self-referential relocation, a destination
 * nested inside its own moved/copied source, an empty delete/move-source span,
 * a no-op replace) throws a plain `Error` with the SAME reason codes the
 * existing direct MOVE/COPY intent path and `patch-compiler.ts` already use
 * (`SOURCE_EQUALS_DESTINATION`, `HIERARCHY_CYCLE_DESTINATION_DESCENDANT`,
 * `NO_OP_PLAN`), never an `AmbientPlannerResponseError` (those are reserved
 * for the ambient model's OWN authoring mistakes, not document drift).
 *
 * ADAPTIVE move/copy without `transformedContent` is already rejected at
 * `parseProposedEdit`'s shape-validation layer (`MALFORMED_DECISION_SHAPE`) --
 * content is never fabricated here either.
 */
export function resolveAmbientCompositeDecisions(
	rawDecisions: readonly unknown[],
	targets: readonly TargetCandidate[],
	state: DocumentState,
): AmbientCompositeResolution {
	const entryIndexOf = new Map(targets.map((t, i) => [t.entryId, i] as const));
	const claimedBy = new Map<number, number>();
	const inPlace: { indices: number[]; parts: AmbientCompositePart[]; actions: EditAction[] } = { indices: [], parts: [], actions: [] };
	const relocation: { indices: number[]; parts: AmbientCompositePart[]; actions: EditAction[] } = { indices: [], parts: [], actions: [] };

	for (const raw of rawDecisions) {
		if (!isRecord(raw)) throw new AmbientPlannerResponseError('MALFORMED_DECISION_SHAPE');
		const allowed = allowedKeysFor(raw.kind);
		if (!allowed) throw new AmbientPlannerResponseError('MALFORMED_DECISION_SHAPE');
		if (unexpectedKeys(raw, allowed).length > 0) throw new AmbientPlannerResponseError('UNEXPECTED_DECISION_FIELD');
		const parsed = parseProposedEdit(raw);
		if (!parsed) throw new AmbientPlannerResponseError('MALFORMED_DECISION_SHAPE');

		const declared = declaredEntryIds(parsed);
		const indices: number[] = [];
		for (const id of declared) {
			const index = entryIndexOf.get(id);
			if (index === undefined) throw new AmbientPlannerResponseError('WRONG_TARGET_ENTRY_ID');
			indices.push(index);
			claimedBy.set(index, (claimedBy.get(index) ?? 0) + 1);
		}

		if (parsed.kind === 'replace') {
			const entry = state.structuralIndex.byId[parsed.targetEntryId];
			if (!entry) throw new Error('UNKNOWN_TARGET');
			const oldText = state.documentBytes.subarray(entry.startByte, entry.endByte).toString('utf8');
			if (oldText === parsed.replacementText) throw new Error('NO_OP_PLAN');
			inPlace.indices.push(...indices);
			inPlace.actions.push(parsed);
			inPlace.parts.push({ entryId: entry.entryId, startByte: entry.startByte, endByte: entry.endByte, textSha256: entry.textSha256, replacementText: parsed.replacementText, op: 'replace' });
		} else if (parsed.kind === 'insert') {
			const anchor = state.structuralIndex.byId[parsed.anchorEntryId];
			if (!anchor) throw new Error('UNKNOWN_TARGET');
			const before = parsed.position === 'before' || parsed.position === 'inside_start';
			const point = before ? anchor.startByte : anchor.endByte;
			inPlace.indices.push(...indices);
			inPlace.actions.push(parsed);
			inPlace.parts.push({ entryId: anchor.entryId, startByte: point, endByte: point, textSha256: EMPTY_TEXT_SHA256, replacementText: parsed.content, op: 'insert', position: before ? 'before' : 'after' });
		} else if (parsed.kind === 'delete') {
			const entry = state.structuralIndex.byId[parsed.targetEntryId];
			if (!entry) throw new Error('UNKNOWN_TARGET');
			if (entry.startByte >= entry.endByte) throw new Error('DELETE_TARGET_EMPTY_SPAN');
			inPlace.indices.push(...indices);
			inPlace.actions.push(parsed);
			inPlace.parts.push({ entryId: entry.entryId, startByte: entry.startByte, endByte: entry.endByte, textSha256: entry.textSha256, replacementText: '', op: 'delete' });
		} else if (parsed.kind === 'move' || parsed.kind === 'copy') {
			const source = state.structuralIndex.byId[parsed.sourceEntryIds[0]!];
			const destination = state.structuralIndex.byId[parsed.destinationAnchorId];
			if (!source || !destination) throw new Error('UNKNOWN_TARGET');
			if (source.entryId === destination.entryId) throw new Error('SOURCE_EQUALS_DESTINATION');
			if (destination.startByte >= source.startByte && destination.endByte <= source.endByte) throw new Error('HIERARCHY_CYCLE_DESTINATION_DESCENDANT');
			if (source.startByte >= source.endByte) throw new Error('SOURCE_TARGET_EMPTY_SPAN');
			const content = parsed.moveMode === 'ADAPTIVE' ? parsed.transformedContent : state.documentBytes.subarray(source.startByte, source.endByte).toString('utf8');
			if (!content) throw new Error('ADAPTIVE_CONTENT_REQUIRED');
			const before = parsed.position === 'before' || parsed.position === 'inside_start';
			const point = before ? destination.startByte : destination.endByte;
			relocation.indices.push(...indices);
			relocation.actions.push(parsed);
			relocation.parts.push({ entryId: destination.entryId, startByte: point, endByte: point, textSha256: EMPTY_TEXT_SHA256, replacementText: content, op: 'insert', position: before ? 'before' : 'after' });
			if (parsed.kind === 'move') {
				relocation.parts.push({ entryId: source.entryId, startByte: source.startByte, endByte: source.endByte, textSha256: source.textSha256, replacementText: '', op: 'delete' });
			}
		} else {
			throw new AmbientPlannerResponseError('MALFORMED_DECISION_SHAPE');
		}
	}

	for (let index = 0; index < targets.length; index++) {
		const count = claimedBy.get(index) ?? 0;
		if (count === 0) throw new AmbientPlannerResponseError('NO_MATCHING_DECISION');
		if (count > 1) throw new AmbientPlannerResponseError('AMBIGUOUS_MATCHING_DECISIONS');
	}

	const toGroup = (group: { indices: number[]; parts: AmbientCompositePart[]; actions: EditAction[] }): AmbientCompositeGroup => {
		const uniqueIndices = [...new Set(group.indices)].sort((left, right) => left - right);
		return { targetIndices: uniqueIndices, targetIds: uniqueIndices.map((index) => targets[index]!.entryId), parts: group.parts, actions: group.actions };
	};

	return { inPlace: toGroup(inPlace), relocation: toGroup(relocation) };
}
