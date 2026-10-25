import { sha256, type PreservationAtom, type PreservationViolation } from "../_core/deliberation/engine/types.js";
import { DOMAIN, proseReference } from "../_core/deliberation/engine/domain-profile.js";

/**
 * This domain's preservation gate implementation (change 4), wired through
 * `profile.ts` as `preservation.{extractAtoms, violations}`. Everything mathematical
 * that used to live in the shared core's `math-integrity.ts` lives here now -- the
 * core only knows about atoms, deltas and violations in the abstract.
 *
 *   1. `extractAtoms` -- which mathematical atoms does the document declare?
 *      Reported on preview via `preservationDelta` (aliased `mathDelta`), and
 *      refused on accept unless the caller acknowledges each lost one by id.
 *   2. `violations` -- does the candidate still spell its mathematics the one way
 *      the `.md` renders correctly? Never intentional, so this blocks outright.
 *
 * `DOMAIN`/`proseReference` are read lazily, inside the functions below, never at
 * this module's own top level: `profile.ts` imports this module to build the
 * `preservation` field `domain-profile.ts` validates, so a top-level read here
 * would race the very profile load that is still in progress.
 */

const short = (value: string) => sha256(value).slice(0, 8);
const collapse = (value: string) => value.replace(/\s+/gu, " ").trim();

/**
 * Unicode ranges that mean "this should have been a LaTeX command". Deliberately
 * narrow: Spanish prose accents, dashes and quotes are untouched, so a violation
 * here is always a real substitution (`ε` for `\varepsilon`), never punctuation.
 */
const GLYPH_RANGES: readonly (readonly [number, number])[] = [
	[0x0370, 0x03ff], // Greek and Coptic
	[0x2070, 0x209f], // super/subscripts
	[0x2100, 0x214f], // letterlike (ℒ ℝ ℕ ℤ ℚ ℂ ℋ)
	[0x2190, 0x21ff], // arrows
	[0x2200, 0x22ff], // mathematical operators
	[0x27c0, 0x27ef], // misc mathematical symbols A
	[0x2980, 0x29ff], // misc mathematical symbols B
	[0x1d400, 0x1d7ff], // mathematical alphanumeric symbols
];
const isMathGlyph = (codePoint: number) => GLYPH_RANGES.some(([lo, hi]) => codePoint >= lo && codePoint <= hi);

/**
 * Marks the bytes that live inside `$…$` or `$$…$$`.
 *
 * The glyph rule applies to notation, and notation is always delimited: prose may
 * legitimately be any Unicode it likes (a title, a Greek word, an arrow in a
 * sentence), and flagging that would block edits that spell nothing wrong. A real
 * substitution -- `ε` where `\varepsilon` belongs -- lands inside the delimiters,
 * which is exactly what this mask keeps in scope.
 */
function mathRegionMask(source: string): Uint8Array {
	const mask = new Uint8Array(source.length);
	for (const match of source.matchAll(/\$\$[\s\S]*?\$\$/gu)) mask.fill(1, match.index, match.index + match[0].length);
	for (const match of source.matchAll(/(?<!\$)\$[^$\n]+\$(?!\$)/gu)) if (!mask[match.index]) mask.fill(1, match.index, match.index + match[0].length);
	return mask;
}

/**
 * Every mathematical atom the source declares, keyed by a stable id.
 *
 * Presence-based, never counted: an atom is only "lost" when it disappears
 * entirely. Rewording a paragraph that happens to repeat `$\sigma$` one time
 * fewer is not a loss of notation, and blocking on it would make the gate
 * useless noise.
 */
export function extractAtoms(source: string): Map<string, PreservationAtom> {
	const proseRef = proseReference("gu");
	const atoms = new Map<string, PreservationAtom>();
	const add = (kind: string, key: string, text: string) => {
		const id = `${kind}:${key}`;
		if (!atoms.has(id)) atoms.set(id, { id, kind, text });
	};
	for (const [, body] of source.matchAll(/\$\$([\s\S]*?)\$\$/gu)) add("display", short(collapse(body)), collapse(body));
	const prose = source.replace(/\$\$[\s\S]*?\$\$/gu, "");
	for (const [, body] of prose.matchAll(/(?<!\$)\$([^$\n]+)\$(?!\$)/gu)) add("inline", short(collapse(body)), collapse(body));
	for (const [, value] of source.matchAll(/\\tag\{([^}]+)\}/gu)) add("tag", value, `\\tag{${value}}`);
	for (const [macro] of source.matchAll(/\\[A-Za-z]+/gu)) add("macro", macro, macro);
	// Finding L5: `proseReferenceText` used to be mandatory at the ENGINE level (`domain-profile.ts`'s
	// `REQUIRED`) even though this is its one reader anywhere -- `experimental-deliberation` had to
	// declare a renderer it never invoked. Now optional there; this module is the one that actually
	// needs it, so it enforces its own requirement, lazily, at the one call site that uses it.
	const proseReferenceText = DOMAIN.proseReferenceText;
	if (!proseReferenceText) throw new Error("PROSE_REFERENCE_TEXT_REQUIRED: this domain's preservation gate renders a citation atom's display text and must declare proseReferenceText.");
	for (const [, value] of source.matchAll(proseRef)) add("ref", value, proseReferenceText(value));
	return atoms;
}

/** The canonical form: how this domain spells mathematics so the `.md` renders. */
export function violations(source: string): PreservationViolation[] {
	const out: PreservationViolation[] = [];
	const lines = source.split("\n");
	if ((source.match(/^\$\$\r?$/gmu)?.length ?? 0) % 2 !== 0)
		out.push({ rule: "display-delimiters-unbalanced", line: 0, detail: "the count of lines that are exactly `$$` is odd" });
	lines.forEach((line, index) => {
		const at = index + 1;
		if (/\$\$.+\$\$/u.test(line))
			out.push({ rule: "display-math-inline", line: at, detail: "display math must open and close on its own `$$` lines, never inside a prose line" });
		// `\\[1em]` is a LaTeX line break with spacing, not a `\[…\]` delimiter: require
		// that the backslash is not itself escaped by a preceding one.
		const delimiter = /(?<!\\)\\[()[\]]/u.exec(line);
		if (delimiter)
			out.push({ rule: "latex-delimiter", line: at, detail: `use $…$ and $$…$$, never ${delimiter[0]}` });
		if (!/\$\$/u.test(line) && (line.match(/\$/gu)?.length ?? 0) % 2 !== 0)
			out.push({ rule: "inline-math-unbalanced", line: at, detail: "an inline `$` opens without closing on the same line" });
	});
	const mask = mathRegionMask(source);
	const flagged = new Set<number>();
	let index = 0, line = 1;
	for (const character of source) {
		if (character === "\n") { line += 1; index += 1; continue; }
		if (mask[index] && isMathGlyph(character.codePointAt(0)!) && !flagged.has(line)) {
			flagged.add(line);
			out.push({ rule: "unicode-math-glyph", line, detail: `${JSON.stringify(character)} must be written as a LaTeX command` });
		}
		index += character.length;
	}
	return out.sort((left, right) => left.line - right.line);
}
