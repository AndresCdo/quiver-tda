import { proseReference } from "../_core/deliberation/engine/domain-profile.js";

/**
 * This domain's reference-integrity vocabulary (change 5), wired through `profile.ts` as
 * `references.{declares, cites}`. Everything LaTeX-specific that used to live directly in
 * the shared core's `candidate-validator.ts`/`reference-index.ts`/`document-index.ts` lives
 * here now -- the core only knows about declared/cited values in the abstract.
 *
 * These documents number with `\tag{N}` and cite in prose as `(Ec. N)` -- `profile.ts`'s own
 * comment on `proseReferencePattern` already says they do not use `\label`/`\eqref` in
 * practice. Both forms are still recognized here (a document that DOES carry a `\label` or
 * an `\eqref` is not malformed, just unusual), so behaviour for every existing fixture stays
 * byte-identical.
 *
 * `proseReference` is read lazily, inside `cites` below, never at this module's own top
 * level: `profile.ts` imports this module to build the `references` field `domain-profile.ts`
 * validates, so a top-level read here would race the very profile load still in progress.
 */

/** Every declaration this domain's documents make: a `\label{id}` or a `\tag{id}`. */
export function declares(source: string): readonly { kind: string; value: string }[] {
	const out: { kind: string; value: string }[] = [];
	for (const [, value] of source.matchAll(/\\label\{([^}]+)\}/g)) out.push({ kind: "label", value });
	for (const [, value] of source.matchAll(/\\tag\{([^}]+)\}/g)) out.push({ kind: "tag", value });
	return out;
}

/** Every citation this domain's documents make: `\eqref{id}`/`\ref{id}`, or this domain's own prose form. */
export function cites(source: string): readonly { kind: string; value: string }[] {
	const out: { kind: string; value: string }[] = [];
	for (const [, kind, value] of source.matchAll(/\\(eqref|ref)\{([^}]+)\}/g)) out.push({ kind, value });
	for (const [, value] of source.matchAll(proseReference("g"))) out.push({ kind: "prose", value });
	return out;
}
