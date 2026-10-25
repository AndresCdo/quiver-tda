import { proseReference } from "../_core/deliberation/engine/domain-profile.js";
import { EXPERIMENT_CONVENTION, IDENTIFIER } from "./experiment-convention.js";

export { EXPERIMENT_CONVENTION };

/**
 * This domain's reference-integrity vocabulary, wired through `profile.ts` as
 * `references.{declares, cites}`. The shared core knows only about declared and
 * cited values in the abstract; what counts as either is stated here.
 *
 * An EXPERIMENT declares an identifier. A CLAIM REFERENCE cites one. That single
 * pair makes both failure directions visible:
 *
 *   - a claim with no experiment behind it cites an identifier nothing declares,
 *     which the core reports as an unresolved reference and fails validation on;
 *   - an experiment mapping to no claim is a declared identifier absent from the
 *     cited set, which `checkReferenceIntegrity` returns alongside the verdict.
 *
 * The declaration kind is the core's own `tag` rather than a domain word, and that
 * is deliberate. `document-index.ts` splits declarations into `entry.labels` and
 * `entry.tags` by exactly those two names, and those arrays feed `deterministicAliases`
 * -- so declaring under `tag` is what lets `RESOLVE_TARGET` select an experiment by
 * its identifier, and what lets `buildReferenceIndex`'s `missing` list resolve
 * instead of reporting every citation as dangling.
 *
 * `proseReference` is read lazily, inside `cites` below, never at this module's own
 * top level: `profile.ts` imports this module to build the `references` field
 * `domain-profile.ts` validates, so a top-level read here would race the very
 * profile load still in progress.
 */

const escape = (literal: string) => literal.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Every declaration this domain's documents make: an experiment naming itself `[exp:E1]`. */
export function declares(source: string): readonly { kind: string; value: string }[] {
	const out: { kind: string; value: string }[] = [];
	for (const [, value] of source.matchAll(new RegExp(`\\[${escape(EXPERIMENT_CONVENTION.declares)}:(${IDENTIFIER})\\]`, "g"))) out.push({ kind: "tag", value });
	return out;
}

/** Every citation this domain's documents make: an explicit `[tests:E1]` claim reference, or the prose form this domain declares. */
export function cites(source: string): readonly { kind: string; value: string }[] {
	const out: { kind: string; value: string }[] = [];
	for (const [, value] of source.matchAll(new RegExp(`\\[${escape(EXPERIMENT_CONVENTION.cites)}:(${IDENTIFIER})\\]`, "g"))) out.push({ kind: "ref", value });
	for (const [, value] of source.matchAll(proseReference("g"))) out.push({ kind: "prose", value });
	return out;
}
