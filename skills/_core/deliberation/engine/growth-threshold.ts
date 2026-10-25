import type { TargetCandidate } from './types.js';

// Growth advisory (design amendment: multi-section successor + growth advisory).
//
// Pure, non-blocking evaluation of ONE already-assembled snapshot of the
// approved-but-not-yet-materialized section targets accumulated during an
// open deliberation. Never reads state, never mutates anything, never
// throws. It IS wired into the live deliberation flow (Phase 2,
// `ChatDeliberationService.deliberate()` in chat-deliberation.ts): the
// service grows the in-session accumulated approved-target set turn-by-turn
// and calls this function every turn to derive the returned
// `growthAdvisory` verdict. This module itself stays a pure function -- it
// only evaluates the snapshot handed to it by the caller.

const MAX_ADVISORY_SECTIONS = 4;
const MAX_ADVISORY_BYTE_RATIO = 0.4;

export type GrowthThresholdSnapshot = Readonly<{
	/** Count of independent (disjoint) approved section targets pending materialization. */
	approvedSectionCount: number;
	/** Sum of approved-target byte spans pending materialization. */
	approvedBytes: number;
	/** Total byte length of the base document the approved targets are measured against. */
	documentBytes: number;
}>;

export type GrowthThresholdVerdict = Readonly<{
	/** Non-blocking: true only recommends materializing a version before continuing. */
	warn: boolean;
	reasons: readonly string[];
}>;

/**
 * Warns (never blocks) when the pending approved set exceeds MORE THAN 4
 * independent sections OR MORE THAN 40% of the document bytes, whichever
 * occurs first. Threshold is "more than", so exactly 4 sections / exactly
 * 40% of document bytes does NOT warn.
 */
export function evaluateSuccessorGrowthThreshold(snapshot: GrowthThresholdSnapshot): GrowthThresholdVerdict {
	const reasons: string[] = [];
	if (snapshot.approvedSectionCount > MAX_ADVISORY_SECTIONS) reasons.push(`approved section count ${snapshot.approvedSectionCount} exceeds ${MAX_ADVISORY_SECTIONS}`);
	const ratio = snapshot.documentBytes > 0 ? snapshot.approvedBytes / snapshot.documentBytes : 0;
	if (ratio > MAX_ADVISORY_BYTE_RATIO) reasons.push(`approved bytes ${snapshot.approvedBytes} exceed ${Math.round(MAX_ADVISORY_BYTE_RATIO * 100)}% of document bytes (${snapshot.documentBytes})`);
	return { warn: reasons.length > 0, reasons };
}

/**
 * Convenience wrapper over `evaluateSuccessorGrowthThreshold` that measures the
 * snapshot directly from a set of resolved composite successor targets (as
 * produced by `resolveSuccessorTarget`/`successorLocusCandidate`) and the
 * document's total byte length, instead of requiring the caller to precompute
 * `approvedSectionCount`/`approvedBytes` itself.
 */
export function evaluateSuccessorGrowthThresholdFromTargets(approvedTargets: readonly Pick<TargetCandidate, 'composite'>[], documentBytes: number): GrowthThresholdVerdict {
	const approvedBytes = approvedTargets.reduce((sum, target) => sum + Math.max(0, (target.composite?.endByte ?? 0) - (target.composite?.startByte ?? 0)), 0);
	return evaluateSuccessorGrowthThreshold({ approvedSectionCount: approvedTargets.length, approvedBytes, documentBytes });
}
