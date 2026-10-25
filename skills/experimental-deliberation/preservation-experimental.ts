import { sha256, type PreservationAtom, type PreservationViolation } from "../_core/deliberation/engine/types.js";

/**
 * This domain's preservation gate, wired through `profile.ts` as
 * `preservation.{extractAtoms, violations}`. The shared core knows only about
 * atoms, deltas and violations in the abstract; everything below is what an
 * EXPERIMENTS document is, and it is deliberately nothing like the mathematical
 * sibling's notation rules.
 *
 *   1. `extractAtoms` -- what does this document declare that must never vanish
 *      in silence? Reported on preview as `preservationDelta`, and refused on
 *      accept unless the caller acknowledges each lost one by id.
 *   2. `violations` -- does the candidate still spell an experiments document the
 *      one way that keeps it honest? Never intentional, so this blocks outright.
 *
 * Nothing here reads `DOMAIN`. That is a property worth keeping rather than an
 * accident: this module can then be exercised directly, in process, under a test
 * run whose single `DELIBERATION_DOMAIN_PROFILE` belongs to another domain.
 *
 * ## Why an experiments document needs its own gate at all
 *
 * The mathematical atom set is worthless here -- an experiments document has no
 * `$$`, no `\tag`, so that extractor returns an empty map and the gate passes
 * vacuously. A vacuous pass is worse than no gate, which is exactly why the core
 * distinguishes "nothing to check" (`preservationApplicable: false`) from
 * "checked and passed", and why the five atom kinds below are the things this
 * document is actually made of.
 */

const short = (value: string) => sha256(value).slice(0, 8);
const collapse = (value: string) => value.replace(/\s+/gu, " ").trim();

/**
 * A GFM table, fully pipe-delimited: a header row, its alignment separator, then
 * zero or more body rows.
 *
 * Byte-identical to `document-index.ts`'s own `GFM_TABLE`, on purpose and not by
 * coincidence: the core indexes a table as its own structural entry (so a table
 * can be a locus), and a gate that recognized a different set of tables would
 * report a loss inside a span the resolver cannot address, or miss one it can.
 * The core does not export it, so it is restated here with this note attached.
 */
const GFM_TABLE = /^\|[^\n]*\|[ \t]*\r?\n\|(?:[ \t]*:?-+:?[ \t]*\|)+[ \t]*\r?\n(?:\|[^\n]*\|[ \t]*(?:\r?\n|$))*/gm;

/** A declared figure placeholder: a Markdown image reference standing alone on its own line. Also restated from `document-index.ts`, same reason. An image reference used inline inside a sentence is prose, not a declared figure. */
const FIGURE_PLACEHOLDER = /^!\[[^\]\n]*\]\([^)\n]*\)[ \t]*$/gm;

/**
 * A declared success criterion: a bold `**Success criterion:**` label, optionally
 * carried by a list bullet, and the criterion itself as the rest of the line.
 *
 * A label rather than a heuristic over prose, because this is the sentence the
 * whole document is answerable to: an experiment whose criterion silently
 * disappeared between two revisions has stopped being falsifiable, and no
 * amount of reading the surrounding paragraph recovers what it used to say.
 */
const SUCCESS_CRITERION = /^[ \t]*(?:[-*+][ \t]+)?\*\*Success criteri(?:on|a):?\*\*[ \t]*(.+?)[ \t]*$/gmu;

/** An external URL. Stops at whitespace, at a closing paren (so a Markdown link target ends where the link does) and at a table cell boundary. */
const EXTERNAL_URL = /https?:\/\/[^\s|)\]]+/gu;

/**
 * A declared label, in the exact bold shape `**Success criterion:**` already uses,
 * plus one widening: the colon may sit inside or outside the bold, and is not
 * captured either way -- `**Dataset**: x` and `**Dataset:** x` key the same
 * declaration. Takes a LITERAL label; never caller text.
 */
const DECLARATION = (label: string) => new RegExp(`^[ \\t]*(?:[-*+][ \\t]+)?\\*\\*${label}:?\\*\\*:?[ \\t]*(.+?)[ \\t]*$`, "gmu");

/** The two declarations an experiments document owes a reader: what it runs on, and how the result will be decided. */
const DATASET = DECLARATION("Dataset");
const VALIDATION_SCHEME = DECLARATION("Validation scheme");

type Declared = { readonly value: string; readonly line: number };

/** Every line matching `pattern`, in document order, with the label stripped and the rest of the line as its value. */
function declarations(source: string, pattern: RegExp): Declared[] {
    const out: Declared[] = [];
    for (const match of source.matchAll(pattern)) {
        const start = match.index ?? 0;
        out.push({ value: (match[1] ?? "").trim(), line: lineAt(source, start) });
    }
    return out;
}

/**
 * The pending-verification convention, and the whole of it.
 *
 * The problem this solves is that the bytes cannot know whether a search ran.
 * "A URL that did not come from a search in the current run must be marked" is
 * only decidable if the ABSENCE of a mark is itself the violation -- so every
 * external URL in an experiments document carries exactly one of two tags,
 * immediately after it, on the same line:
 *
 *   - `[pending-verification]`      -- nobody has reached this URL yet.
 *   - `[verified: YYYY-MM-DD]`      -- a search in the run of that date reached it.
 *
 * An untagged URL is refused. That is the point: the default is the violation,
 * so a URL a model invented from memory cannot be published by saying nothing,
 * and the run date makes a stale verification visible instead of permanent. The
 * date must be a full `YYYY-MM-DD`; a bare year is not a run.
 *
 * "Immediately after" is load-bearing too. A tag anywhere on the line would let
 * one verified URL vouch for an unverified neighbour, so the tag must be the
 * next non-blank thing after the URL ends. The only bytes allowed to sit between
 * them are the ones the URL was wrapped in or ended by: a Markdown link's closing
 * paren and ordinary sentence punctuation. Citing a repository as
 * `[the repository](https://example.org/x) [pending-verification]` is the normal
 * way to write one, and a rule that refused it would be a rule nobody could obey.
 */
const VERIFICATION_TAG_SOURCE = "\\[pending-verification\\]|\\[verified: \\d{4}-\\d{2}-\\d{2}\\]";
const VERIFICATION_TAG_FOLLOWS = new RegExp(`^[)\\].,;:!?]*[ \\t]*(?:${VERIFICATION_TAG_SOURCE})`, "u");
const VERIFICATION_TAG_ANYWHERE = new RegExp(VERIFICATION_TAG_SOURCE, "gu");

/**
 * The `dataset` atom's key: `atom.text` keeps the declared line's original
 * casing, but the id two authors of the same dataset would echo back has to be
 * the same id even when they wrote it slightly differently. Four steps, each
 * meaning-preserving, each with a precedent already in this file:
 *
 *   1. Strip a verification tag (`VERIFICATION_TAG_ANYWHERE`) -- load-bearing:
 *      the URL rule FORCES a tag onto any dataset line citing a URL, so a real
 *      re-verification would flip `[pending-verification]` -> `[verified: …]`
 *      and read as a dataset SWAP if the tag were part of the key.
 *   2. Strip trailing sentence punctuation (`externalUrls`' own class).
 *   3. Collapse whitespace -- a reflow is not a swap.
 *   4. Case-fold -- `ImageNet` and `imagenet` are never two datasets.
 *
 * Nothing else is normalized: dropping more would let a genuine split change
 * (`(train/test)` -> `(train/val)`) pass as unchanged, which is the failure
 * this key exists to catch.
 */
function normalizeDatasetKey(value: string): string {
    const withoutTag = value.replace(VERIFICATION_TAG_ANYWHERE, " ");
    const withoutTrailingPunctuation = withoutTag.replace(/[.,;:!?]+$/u, "");
    return collapse(withoutTrailingPunctuation).toLowerCase();
}

/**
 * Every token/phrase this file's validation-scheme check needs to recognize by
 * exact word or phrase -- never by substring, since this project has already
 * been burned by a stopword that matched inside an unrelated word.
 */
const PLACEHOLDERS = ["tbd", "to be decided", "to be determined", "tba", "n/a", "na", "none", "pending", "todo", "xxx", "?", "-"];
const NON_TEST_OUTPUTS = ["p value", "pvalue", "significance", "statistical significance", "confidence interval", "effect size"];
const CONNECTIVES = ["a", "an", "the", "and", "or", "with", "over", "across", "on", "in", "at", "per", "of", "for", "from", "using", "use", "used", "to", "by", "plus", "then", "each"];
/** Ruling 7: the literal word `seeds` is not the only correct way to name the count -- `semillas`, `initialisations`, `runs`, `trials` and `folds` all satisfy it. The COUNT itself must be a digit token (`10 random initialisations`, never `ten`): a spelled-number vocabulary would go stale in exactly the way the closed test-name vocabulary was rejected for. */
const SEEDS_TERMS = new Set(["seed", "seeds", "semilla", "semillas", "initialisation", "initialisations", "initialization", "initializations", "run", "runs"]);
const REPETITION_TERMS = new Set(["repetition", "repetitions", "repeat", "repeats", "repeated", "replicate", "replicates", "replication", "replications", "run", "runs", "trial", "trials", "fold", "folds"]);

/** Hyphens between two letters folded to a space (`p-value` -> `p value`), so a hyphenated test name and its spaced-out spelling key the same clause. A hyphen NOT between two letters (a bare `-` placeholder, a numeric range) is untouched. */
function foldHyphens(value: string): string {
    return value.replace(/(\p{L})-(?=\p{L})/gu, "$1 ");
}

/** Every maximal run of letters/digits, lowercased input assumed -- the token grain every check below reasons in, so a stopword can only match a WHOLE token, never a substring inside one. */
function tokensOf(value: string): string[] {
    return value.match(/[\p{L}\p{N}]+/gu) ?? [];
}

/** Removes `phrase`, as a whole phrase bounded by non-alphanumeric characters (never a substring match), everywhere it occurs in `value`. */
function removePhrase(value: string, phrase: string): string {
    const escaped = phrase.replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
    return value.replace(new RegExp(`(?<![\\p{L}\\p{N}])${escaped}(?![\\p{L}\\p{N}])`, "gu"), " ");
}

function removePhrases(value: string, phrases: readonly string[]): string {
    return phrases.reduce((acc, phrase) => removePhrase(acc, phrase), value);
}

/** The value's clauses: split on `,`/`;`, trimmed, blanks dropped. Clause-scoped, not value-scoped, so "fixed seeds" in one clause cannot borrow a digit that belongs to a different clause's "3 repetitions". */
function clauses(value: string): string[] {
    return value.split(/[,;]/u).map((clause) => clause.trim()).filter((clause) => clause.length > 0);
}

/** A clause names its own digit-bearing seeds count, on its own -- borrowing no digit from a neighbour. */
function isSeedsClause(clause: string): boolean {
    const tokens = tokensOf(clause);
    return tokens.some((token) => SEEDS_TERMS.has(token)) && tokens.some((token) => /^\d+$/u.test(token));
}

/** A clause names its own digit-bearing repetition count, on its own. */
function isRepetitionsClause(clause: string): boolean {
    const tokens = tokensOf(clause);
    return tokens.some((token) => REPETITION_TERMS.has(token)) && tokens.some((token) => /^\d+$/u.test(token));
}

/**
 * What is left of the value once every placeholder, non-test-output and
 * connective PHRASE is stripped, and every bare numeral and seeds/repetitions
 * VOCABULARY TOKEN is stripped with it.
 *
 * Not vocabulary -- REDUCTION. There is no closed list of test names; the
 * question this answers is only whether anything survives being explained
 * away, never whether what survives IS a real test.
 *
 * Token-scoped rather than clause-scoped, on purpose: `t-test over 5 seeds`
 * names its test and its seeds count in the SAME clause (no comma separates
 * them), so excluding that whole clause once it satisfies the seeds check
 * would destroy the test name along with it -- exactly the false block a
 * clause-exclusion design produces and this one does not.
 */
function testResidue(normalizedValue: string): string {
    let residue = normalizedValue;
    residue = removePhrases(residue, PLACEHOLDERS);
    residue = removePhrases(residue, NON_TEST_OUTPUTS);
    residue = removePhrases(residue, CONNECTIVES);
    return tokensOf(residue)
        .filter((token) => !/^\d+$/u.test(token) && !SEEDS_TERMS.has(token) && !REPETITION_TERMS.has(token))
        .join(" ");
}

/**
 * The validation-scheme content check (D4), run only when exactly one
 * `**Validation scheme:**` line exists. `(a)` short-circuits `(b)` and `(c)`:
 * a declaration that names no test cannot be judged for its seeds.
 */
function validationSchemeContentViolation(value: string): { rule: string; detail: string } | null {
    const normalized = foldHyphens(value).toLowerCase();
    if (testResidue(normalized) === "")
        return {
            rule: "validation-scheme-without-test",
            detail: `${JSON.stringify(value)} names no statistical test once placeholders, non-test outputs, connectives, matched seeds/repetitions clauses and bare numerals are set aside; name the test, e.g. "paired t-test"`,
        };
    if (!clauses(normalized).some(isSeedsClause))
        return {
            rule: "validation-scheme-without-seeds",
            detail: `${JSON.stringify(value)} names no seeds clause; one clause must carry both a seeds token (seeds, semillas, initialisations, initializations, runs) and a digit, e.g. "5 seeds"`,
        };
    if (!clauses(normalized).some(isRepetitionsClause))
        return {
            rule: "validation-scheme-without-repetitions",
            detail: `${JSON.stringify(value)} names no repetitions clause; one clause must carry both a repetitions token (repetitions, repeats, replications, runs, trials, folds) and a digit, e.g. "10 repetitions"`,
        };
    return null;
}

/**
 * Cardinality (D2): zero and two-or-more are different facts and get
 * different ids. `line: 1` for an absence -- there is no offending line,
 * `violations()` sorts by line, and a missing declaration then sorts first,
 * which is the right reading order.
 */
type Cardinality = { readonly kind: "missing" } | { readonly kind: "repeated"; readonly lines: readonly number[] };

function cardinalityOf(found: readonly Declared[]): Cardinality | null {
    if (found.length === 0) return { kind: "missing" };
    if (found.length > 1) return { kind: "repeated", lines: found.map((d) => d.line) };
    return null;
}

/** `declared on lines 4, 9; exactly one \`**<label>:**\` line is required, and the engine must not pick one silently` -- the shared detail shape both repeated-declaration ids use. */
function repeatedDetail(labelText: string, lines: readonly number[]): string {
    return `declared on lines ${lines.join(", ")}; exactly one \`**${labelText}:**\` line is required, and the engine must not pick one silently`;
}

/**
 * The first header cell that makes a table a BASELINES table rather than a report
 * table, and the distinction the fabricated-value rule below rests on.
 *
 * A report table is a promise about a future run: its body cells are slots, and a
 * number in one is a result nobody measured. A baselines table is a reference:
 * its cells legitimately carry a repository, a venue and a year. One header cell
 * tells them apart, and it is the only thing that does.
 */
const BASELINE_COLUMNS = new Set(["baseline", "baselines"]);

/**
 * The first header cell that makes a table a PARAMETERS table: a declaration of the settings
 * the plan fixes (a learning rate, a batch size, a seed list), not a promise about a run. Its
 * values are decided now, by the plan, so a number in one is not a result anybody measured and
 * the fabricated-value rule does not apply. Same discipline as the baselines header: the WHOLE
 * first header cell, case-insensitively, and nothing else declares it -- `Parameter count` or a
 * `Parameter` column further right is an ordinary report table, and keeps the rule.
 */
const PARAMETER_COLUMNS = new Set(["parameter", "parameters", "hyperparameter", "hyperparameters"]);

/** A venue year. Narrow on purpose: a four-digit year in the 1900s or 2000s, which is what a conference or journal citation carries. */
const VENUE_YEAR = /\b(?:19|20)\d{2}\b/u;

type TableRow = { readonly line: number; readonly cells: readonly string[] };
type ParsedTable = { readonly line: number; readonly header: string; readonly body: readonly TableRow[]; readonly baselines: boolean; readonly parameters: boolean };

/** A pipe-delimited row split into its cells, with the outer pipes dropped and every cell trimmed. */
function cellsOf(row: string): string[] {
    return row.trim().replace(/^\|/u, "").replace(/\|$/u, "").split("|").map((cell) => cell.trim());
}

/** The 1-based line an index falls on. */
function lineAt(source: string, index: number): number {
    let line = 1;
    for (let at = 0; at < index; at += 1) if (source[at] === "\n") line += 1;
    return line;
}

/** Every GFM table in the source, already split into a header, its body rows and their line numbers. */
function tables(source: string): ParsedTable[] {
    const out: ParsedTable[] = [];
    for (const match of source.matchAll(GFM_TABLE)) {
        const start = match.index ?? 0;
        const lines = match[0].split(/\r?\n/u);
        const header = (lines[0] ?? "").trim();
        const headerCells = cellsOf(header);
        const body: TableRow[] = [];
        // Row 0 is the header and row 1 is the alignment separator; the body starts at 2.
        for (let offset = 2; offset < lines.length; offset += 1) {
            const raw = lines[offset] ?? "";
            if (!raw.trim()) continue;
            body.push({ line: lineAt(source, start) + offset, cells: cellsOf(raw) });
        }
        out.push({ line: lineAt(source, start), header, body, baselines: isBaselinesTable(headerCells), parameters: PARAMETER_COLUMNS.has((headerCells[0] ?? "").toLowerCase()) });
    }
    return out;
}

/** Whether this table's first header cell declares it a baselines table. */
function isBaselinesTable(headerCells: readonly string[]): boolean {
    return BASELINE_COLUMNS.has((headerCells[0] ?? "").toLowerCase());
}

type FoundUrl = { readonly value: string; readonly line: number; readonly trailing: string };

/** Every external URL, with the rest of its own line, so the tag rule can ask what immediately follows. */
function externalUrls(source: string): FoundUrl[] {
    const out: FoundUrl[] = [];
    for (const match of source.matchAll(EXTERNAL_URL)) {
        const start = match.index ?? 0;
        // Sentence punctuation is not part of a URL: `…/alpha-net.` cites `…/alpha-net`,
        // and the stripped character stays in `trailing`, where it correctly fails the tag rule.
        const value = match[0].replace(/[.,;:!?]+$/u, "");
        const end = start + value.length;
        const lineEnd = source.indexOf("\n", end);
        out.push({ value, line: lineAt(source, start), trailing: source.slice(end, lineEnd < 0 ? source.length : lineEnd) });
    }
    return out;
}

/**
 * Every atom this document declares, keyed by a stable id.
 *
 * Presence-based, never counted, exactly as the mathematical sibling argues:
 * an atom is lost only when it disappears entirely, so rewording a paragraph
 * that happened to repeat a figure reference is not a loss.
 *
 *   `report-table`     a table's header row -- the skeleton that declares what will be reported
 *   `baseline`         a model named in the first cell of a baselines table's body row
 *   `success-criterion` a declared criterion the document is answerable to
 *   `figure`           a figure placeholder standing alone on its own line
 *   `url`              a cited external URL, keyed by the URL itself
 *   `dataset`          a declared `**Dataset:**` line, keyed by its normalized text (D3) --
 *                      so a silent swap between two versions surfaces as a loss to acknowledge,
 *                      not merely a line that still exists. The validation scheme takes no
 *                      atom (ruled): it is a hard block only.
 */
export function extractAtoms(source: string): Map<string, PreservationAtom> {
    const atoms = new Map<string, PreservationAtom>();
    const add = (kind: string, key: string, text: string) => {
        const id = `${kind}:${key}`;
        if (!atoms.has(id)) atoms.set(id, { id, kind, text });
    };
    for (const table of tables(source)) {
        add("report-table", short(collapse(table.header)), collapse(table.header));
        if (!table.baselines) continue;
        for (const row of table.body) {
            const name = collapse(row.cells[0] ?? "");
            if (name) add("baseline", short(name), name);
        }
    }
    for (const [placeholder] of source.matchAll(FIGURE_PLACEHOLDER)) add("figure", short(collapse(placeholder)), collapse(placeholder));
    for (const [, criterion] of source.matchAll(SUCCESS_CRITERION)) add("success-criterion", short(collapse(criterion)), collapse(criterion));
    // Keyed by the URL itself rather than by a digest: the id is what a caller has
    // to echo back to authorise a removal, and a citation is legible where a hash is not.
    for (const found of externalUrls(source)) add("url", found.value, found.value);
    // Keyed by its own normalized text (D3), same reason as `url` -- the id a caller
    // echoes back to authorise a loss has to be legible.
    for (const declared of declarations(source, DATASET)) add("dataset", normalizeDatasetKey(declared.value), collapse(declared.value));
    return atoms;
}

/** The canonical form: how this domain writes an experiments document so it stays honest about what has not happened yet. */
export function violations(source: string): PreservationViolation[] {
    const out: PreservationViolation[] = [];
    for (const table of tables(source)) {
        for (const row of table.body) {
            if (table.baselines) {
                baselineViolations(row, out);
                continue;
            }
            // A declaration of the plan's own settings, not a slot for a result.
            if (table.parameters) continue;
            row.cells.forEach((cell, column) => {
                // Column one is the row LABEL -- what is being reported on, not a reported
                // value -- so `Adapted (k=3)` is a name and not a result. Everything past it
                // is a slot a future run fills, and a number in one is a fabricated result.
                if (column === 0 || !/\d/u.test(cell)) return;
                out.push({
                    rule: "report-table-fabricated-value",
                    line: row.line,
                    detail: `column ${column + 1} of this report table must stay empty until a run fills it; found ${JSON.stringify(cell)}`,
                });
            });
        }
    }
    for (const found of externalUrls(source))
        if (!VERIFICATION_TAG_FOLLOWS.test(found.trailing))
            out.push({
                rule: "url-without-verification-marker",
                line: found.line,
                detail: `${found.value} must be followed by [pending-verification] or [verified: YYYY-MM-DD]; an unmarked URL claims a search that left no trace`,
            });
    datasetViolations(source, out);
    validationSchemeViolations(source, out);
    return out.sort((left, right) => left.line - right.line);
}

/**
 * The dataset declaration (D1-D2, ruling 6): exactly one `**Dataset:**` line,
 * and it must not reduce to a denylisted placeholder -- the identical denylist
 * the validation scheme uses, because a presence rule alone guarantees a line
 * EXISTS, never that it SAYS anything.
 */
function datasetViolations(source: string, out: PreservationViolation[]): void {
    const found = declarations(source, DATASET);
    const cardinality = cardinalityOf(found);
    if (cardinality?.kind === "missing") {
        out.push({
            rule: "dataset-declaration-missing",
            line: 1,
            detail: "an experiments document declares its data once, as `**Dataset:** <name and split>` on its own line; a label with nothing after it declares nothing",
        });
        return;
    }
    if (cardinality?.kind === "repeated") {
        out.push({ rule: "dataset-declaration-repeated", line: found[1].line, detail: repeatedDetail("Dataset", cardinality.lines) });
        return;
    }
    const [only] = found;
    if (only && isPlaceholderOnly(only.value))
        out.push({
            rule: "dataset-declaration-missing",
            line: only.line,
            detail: `${JSON.stringify(only.value)} reduces to a placeholder once the same denylist the validation scheme uses is set aside; a placeholder declares nothing, exactly like an empty label`,
        });
}

/** Ruling 6: the dataset takes the identical denylist the validation scheme uses (D4's `PLACEHOLDERS`) -- a presence rule alone guarantees the line EXISTS, never that it SAYS anything. */
function isPlaceholderOnly(value: string): boolean {
    const normalized = foldHyphens(value).toLowerCase();
    return tokensOf(removePhrases(normalized, PLACEHOLDERS)).length === 0;
}

/** The validation-scheme declaration (D2, D4): exactly one line, naming a test, its seeds and its repetitions. */
function validationSchemeViolations(source: string, out: PreservationViolation[]): void {
    const found = declarations(source, VALIDATION_SCHEME);
    const cardinality = cardinalityOf(found);
    if (cardinality?.kind === "missing") {
        out.push({
            rule: "validation-scheme-declaration-missing",
            line: 1,
            detail: "an experiments document declares its validation scheme once, as `**Validation scheme:** <test, seeds, repetitions>` on its own line, naming a statistical test, its seeds and its repetitions; a label with nothing after it declares nothing",
        });
        return;
    }
    if (cardinality?.kind === "repeated") {
        out.push({ rule: "validation-scheme-declaration-repeated", line: found[1].line, detail: repeatedDetail("Validation scheme", cardinality.lines) });
        return;
    }
    const [only] = found;
    if (!only) return;
    const content = validationSchemeContentViolation(only.value);
    if (content) out.push({ rule: content.rule, line: only.line, detail: content.detail });
}

/** A named baseline owes a reader two things: where the code is, and where the work was published. */
function baselineViolations(row: TableRow, out: PreservationViolation[]): void {
    const name = collapse(row.cells[0] ?? "");
    if (!name) return;
    const text = row.cells.join(" | ");
    // The verification tag carries a date, and a date carries a year. Left in, a
    // freshly verified URL would satisfy the venue check on a row that names no venue.
    const withoutTags = text.replace(VERIFICATION_TAG_ANYWHERE, " ");
    if (!/https?:\/\//u.test(text))
        out.push({ rule: "baseline-missing-repository-url", line: row.line, detail: `the baseline ${JSON.stringify(name)} names no repository URL` });
    if (!VENUE_YEAR.test(withoutTags))
        out.push({ rule: "baseline-missing-venue-year", line: row.line, detail: `the baseline ${JSON.stringify(name)} names no venue year` });
}
