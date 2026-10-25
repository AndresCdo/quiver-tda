import { readFileSync } from "node:fs";

/**
 * The experiment convention, read from the ONE file both experimental skills share:
 * `skills/_core/conventions/experiments.json`. `experimental-implementation`'s
 * `impl_profile.py` reads the same file, so the identifier class, the declaration and
 * citation markers and the prose form cannot drift between the skill that writes an
 * experiments document and the skill that implements it.
 *
 * A module of its own, importing nothing from the core: `profile.ts` reads
 * `PROSE_REFERENCE_PATTERN` while the core is still loading that very profile, so
 * this value must not sit behind the core's own import (`reference-experimental.ts`
 * imports `domain-profile.ts`, which is what loads `profile.ts`).
 */
export const EXPERIMENT_CONVENTION: Readonly<{ identifier: string; declares: string; cites: string; proseReference: string }> =
	JSON.parse(readFileSync(new URL("../_core/conventions/experiments.json", import.meta.url), "utf8"));

/** An experiment identifier: alphanumeric, and hyphens, dots or underscores after the first character. */
export const IDENTIFIER = EXPERIMENT_CONVENTION.identifier;

/** The prose citation pattern, one capturing group: `(Exp. E1)` / `(Experiment. E1)` under the shipped convention. */
export const PROSE_REFERENCE_PATTERN = EXPERIMENT_CONVENTION.proseReference.split("{identifier}").join(IDENTIFIER);
