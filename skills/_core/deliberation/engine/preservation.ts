import { DOMAIN } from './domain-profile.js';
import type { PreservationAtom, PreservationDelta, PreservationViolation } from './types.js';

/**
 * The preservation gate (change 4): what a document must never lose in silence, and
 * the canonical form every byte it stores must keep. Formerly `math-integrity.ts` --
 * domain-neutral now, sourcing its atom extractor and rule set from
 * `profile.preservation.{extractAtoms, violations}` instead of hardcoding one
 * domain's own subject. The mathematical implementation ships as
 * `the host-chosen profile's own preservation module`, wired through that profile.
 *
 * The engine's other validators check *internal consistency* -- that labels are
 * unique, that references target existing entries, that symbols do not conflict.
 * None of them check *preservation*: a locus rewrite that drops an atom outright
 * passes every one of them, because what remains is still perfectly consistent.
 * Byte coverage only guards the bytes OUTSIDE the resolved locus, which is exactly
 * where the loss is not.
 *
 * So this module answers two different questions:
 *
 *   1. `delta`      -- which atoms existed before and are now gone?
 *                      Reported on preview, and refused on accept unless the
 *                      caller acknowledges each one by id.
 *   2. `violations` -- does the candidate still spell its notation the one way
 *                      the `.md` renders correctly? Never intentional, so this
 *                      blocks outright.
 */

/** Every atom `source` declares, per the host profile's own extractor. Empty when the profile's vocabulary recognizes nothing -- the caller must report that as "not applicable", never as a vacuous pass (see `candidate-validator.ts`'s `preservationApplicable`). */
export function atoms(source: string): Map<string, PreservationAtom> {
	return DOMAIN.preservation.extractAtoms(source);
}

/**
 * Atoms present before and absent after (and the reverse).
 *
 * Compares whole documents rather than the resolved locus, which is equivalent
 * and far more robust: everything outside the locus is byte-identical by
 * `unchangedByteCoverage`, so any atom missing from the whole document went
 * missing inside the locus.
 */
export function delta(before: string, after: string): PreservationDelta {
	const a = atoms(before), b = atoms(after);
	return {
		lost: [...a.values()].filter(atom => !b.has(atom.id)),
		added: [...b.values()].filter(atom => !a.has(atom.id)),
	};
}

/** The canonical-form rules this profile's own notation must never violate. */
export function violations(source: string): PreservationViolation[] {
	return DOMAIN.preservation.violations(source);
}
