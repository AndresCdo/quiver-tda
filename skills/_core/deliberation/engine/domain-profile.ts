import { isAbsolute } from "node:path";
import type { PreservationAtom, PreservationViolation } from "./types.js";

/**
 * The contract a deliberation domain fills in, and the resolver that finds it.
 *
 * This engine is shared. It manages revisions of a Markdown document, indexes it,
 * patches it byte-exactly and transacts the result -- none of which is specific to
 * what the document argues about. What IS specific lives in a profile the HOST
 * chooses, never here: the engine that names a domain is an engine only one skill
 * can use.
 *
 * There is deliberately no default. A default would have to name one domain, which
 * is the exact coupling this file exists to remove, and a silent fallback is worse
 * than a refusal: the caller would get a working engine quietly answering for the
 * wrong document. Each skill ships a launcher that sets the variable.
 */
export type DeliberationDomainProfile = {
	/** The single file `derive` and `derive_revision` accept as a source. */
	readonly deriveBase: string;
	/** How a refusal names that file mid-sentence: "... is missing from the X." */
	readonly baseLabel: string;
	/** The same file, named where the sentence needs the longer form. */
	readonly baseLabelLong: string;
	/** A well-formed revision slug, shown to the caller when it supplies a malformed one. */
	readonly exampleSlug: string;
	/**
	 * Every word that belongs to this domain and to no other.
	 *
	 * The lock in `the core-scan lock (`no file in the shared core names any domain`)`
	 * refuses any engine file outside this one that contains any of them, matched
	 * case-insensitively. Checking only the composed values above is not enough:
	 * `exampleSlug` carries the same proper noun in lowercase, and that residue
	 * survived a phrase-by-phrase sweep precisely because it was spelled
	 * differently everywhere it appeared.
	 */
	readonly names: readonly string[];
	/**
	 * How this domain's documents cite their own numbered displays in prose.
	 *
	 * A source string rather than a RegExp, because two call sites need it with
	 * different flags and a shared mutable RegExp carries `lastIndex` between
	 * them. Both used to spell this pattern out separately -- `reference-index.ts`
	 * and the module now named `preservation-math.ts` -- with two literals that
	 * agreed only by luck.
	 */
	readonly proseReferencePattern: string;
	/**
	 * The same citation, written back out for an atom's display text.
	 *
	 * Optional (finding L5): no file under `_core/` ever reads this -- its one real
	 * reader anywhere is one host's own preservation module, for the "ref" atom kind
	 * its own gate extracts. A host with no "ref" atom kind at all used to be forced to
	 * declare a renderer it never invoked anyway (this field was in `REQUIRED` below);
	 * that host's own preservation module documents, on purpose, that it reads no
	 * `DOMAIN` field at all. A mandatory engine-level field with a real reader in
	 * exactly one host is that host's OWN requirement, not the engine's, so it is
	 * enforced there (that module's own lazy read) instead of here.
	 */
	readonly proseReferenceText?: (value: string) => string;
	/**
	 * What this domain's instructions are ABOUT.
	 *
	 * The engine's intent matching is Spanish, and that part is shared: every
	 * deliberation domain says "mueve", "copia", "agrega". What is not shared is
	 * the subject -- one document argues about regularisation and one-hot
	 * encoding, another about baselines and ablations -- and that subject was
	 * spelled directly into intent resolution, locus scoring and the tutor gate.
	 */
	readonly vocabulary: {
		/** Subject words that make an instruction this domain's own conceptual work. */
		readonly conceptualTerms: readonly string[];
		/** Requires the domain expert before a conceptual plan is built. */
		readonly expertPattern: string;
		/** How a locus query names one of this domain's numbered displays. */
		readonly displayNounPattern: string;
		/** The same noun with its inflections, stripped out of a successor query. */
		readonly displayNounStripPattern: string;
		/** What this document is about, used to bias locus scoring. */
		readonly subjectPattern: string;
		/** Terms naming that subject directly in an instruction. */
		readonly subjectTerms: readonly string[];
		/** The locus description used when an instruction names the subject. */
		readonly subjectLocusDescription: string;
		/** How scoring reports that a neighbouring entry defines the subject. */
		readonly subjectEvidenceLabel: string;
		/**
		 * Optional (change 10): equivalent to the core `'sparse'`/`'dispers'` literal this
		 * change removes from `intent-resolver.ts`. When declared, an instruction matching any
		 * of `terms` (plain substring, same matching style as every other `has(...)` check in
		 * `intent-resolver.ts`) reports `requestedEffect: label`, exactly as the removed literal
		 * did. Undeclared is equally valid: `requestedEffect` is then simply never set by this
		 * mechanism, which is acceptable because nothing downstream reads it except the
		 * conceptual plan's `scientificGoal` fallback.
		 */
		readonly requestedEffect?: { readonly terms: readonly string[]; readonly label: string };
	};
	/**
	 * The complete managed-artifact namespace this domain claims. Nothing here may be
	 * substituted with a default: `artifact-naming.ts` is the only file that reads these
	 * values back out, and it is the only file in core allowed to spell the resulting names.
	 */
	readonly artifact: {
		/** Where managed revisions live, relative to the project root (e.g. a single lowercase noun naming the artifact kind). */
		readonly directory: string;
		/** The managed filename's fixed prefix (e.g. that same noun, used as the stem). */
		readonly stem: string;
		/** The revision label's own prefix, escaped and composed by `artifact-naming.ts` -- never a full regex (e.g. a single letter). */
		readonly revisionPattern: string;
		/** Renders a revision ordinal into its full label (e.g. ordinal 6 into a two-digit-padded label). */
		readonly revisionLabel: (ordinal: number) => string;
		/** Where sidecar state/receipts/withdrawn records live, relative to the project root (e.g. a dot-prefixed sidecar directory name). */
		readonly sidecarRoot: string;
		/** The exact managed-artifact marker bytes, including its trailing newline. */
		readonly marker: string;
		/**
		 * Change 8, option (b): the change header is its OWN resolved block span, gated on this
		 * field's presence -- never a sidecar-only field, never an invariant exemption.
		 * `COMPOSITE_UNTOUCHED_INVARIANT` (`successor-composite-engine.ts`) walks only the gaps
		 * BETWEEN edit spans plus the tail; a header that IS its own span sits inside the union,
		 * so the invariant is satisfied, not bypassed. Undeclared (the default, and
		 * the mathematical domain's own choice): `CREATE_SUCCESSOR` requires nothing extra,
		 * `renderFromIdea` emits nothing extra, bytes are byte-identical to pre-change behavior.
		 */
		readonly changeHeader?: {
			/** The exact heading text (no leading `#`s) `initial-revision-renderer.ts` renders in v1 and `orchestrator.ts` locates as the header's own structural entry on every successor. */
			readonly heading: string;
			/** Renders the FULL header block -- including its own heading line -- from the caller's `changeSummary`. Replaces the header entry's entire span each version; the receipt is where full history lives. */
			readonly render: (summary: { readonly what: string; readonly why: string }) => string;
		};
		/**
		 * Finding L6: `initial-revision-renderer.ts` used to hardcode `## Paper Guide
		 * Reference` above every loaded read-only source fragment in v1, regardless of
		 * domain -- accurate for a domain whose one source really is a paper guide, and
		 * wrong for a domain whose declared sources never are. Undeclared (the default,
		 * matching that first domain's own choice) renders the exact prior literal, zero
		 * migration.
		 */
		readonly sourceReferenceHeading?: string;
		/**
		 * Finding L6: `successor-edit-planner.ts` used to hardcode `## Accepted scientific
		 * decisions` for its claim-provenance document-tail summary block, undeclared by
		 * any profile. Undeclared (the default) renders the exact prior literal, zero
		 * migration for either shipped host.
		 */
		readonly acceptedDecisionsHeading?: string;
	};
	/**
	 * Change 9: names which loaded sources this domain treats as a hard bound on claims, and
	 * how to detect a candidate's evidence contradicting one. Off by default -- a profile
	 * declaring none (the mathematical domain's own choice) never raises
	 * `SOURCE_AUTHORITY_CONFLICT`, regardless of candidate content. `severity` defaults to
	 * `'advisory'` (preview-time, cleared by `acknowledgedSourceConflicts` on accept, mirroring
	 * the preservation gate); `'refuse'` hard-blocks publish outright instead.
	 */
	readonly sourceAuthority?: {
		/** Which of `sources`' paths this domain treats as a bound, for identification in a reported conflict. */
		readonly names: readonly string[];
		/** Pure detector over the candidate's full document text -- the profile already knows what its own bound source asserts, exactly as `preservation.extractAtoms` already knows its own canonical notation, with no engine-level file I/O. Empty when nothing conflicts. */
		readonly detectConflicts: (candidateText: string) => readonly { readonly id: string; readonly sourceName: string; readonly claim: string; readonly evidence: string }[];
		/** `'advisory'` (default) or `'refuse'`. */
		readonly severity?: 'advisory' | 'refuse';
	};
	/**
	 * The preservation gate's atom extractor and rule set (change 4): `preservation.ts`
	 * (formerly `math-integrity.ts`) is domain-neutral and sources both from here instead of
	 * hardcoding one domain's own subject. The mathematical implementation ships as
	 * `the host-chosen profile's own preservation module`, wired through this field.
	 */
	readonly preservation: {
		/** Every atom `source` declares, keyed by a stable id. Empty when nothing in this domain's vocabulary is present -- the caller (`preservation.ts`) reports that as "not applicable", never as a vacuous pass. */
		readonly extractAtoms: (source: string) => Map<string, PreservationAtom>;
		/** The canonical-form rules this domain's own notation must never violate -- never intentional, so these block outright rather than requiring acknowledgement. */
		readonly violations: (source: string) => PreservationViolation[];
	};
	/**
	 * Reference integrity (change 5): what this domain's documents DECLARE as a numbered/named
	 * thing, and what CITES one, sourced here instead of hardwiring `\label`/`\tag`/`\eqref`/
	 * `(Ec. N)` into `candidate-validator.ts`, `reference-index.ts` and `document-index.ts`.
	 * The mathematical vocabulary ships as `the host-chosen profile's own reference module`, wired
	 * through this field, exactly as `preservation` ships `preservation-math.ts` above.
	 */
	readonly references: {
		/** Every declaration this domain's documents make, each carrying its declaration kind (e.g. "label"/"tag" for math -- read by `document-index.ts` to keep its own `entry.labels`/`entry.tags` split for locus lookup) and the declared value. Two declarations sharing a value are a duplicate. Empty when nothing in this text matches the domain's vocabulary -- the caller reports that as "not applicable", never as a vacuous pass. */
		readonly declares: (source: string) => readonly { readonly kind: string; readonly value: string }[];
		/** Every citation this domain's documents make of a declared thing, each carrying its citation form and the cited value. A citation whose value never appears in `declares`'s output is unresolved. */
		readonly cites: (source: string) => readonly { readonly kind: string; readonly value: string }[];
	};
	/**
	 * Read-only reference sources (change 7), loaded once before a NEW deliberation's first
	 * revision renders. Replaces the single hardcoded `GUIDE_DIRECTORY` path in
	 * `proposal-workspace.ts`: each `path` is a project-root-relative directory inventoried the
	 * same way the legacy single guide was, and a `required: true` source that is absent blocks
	 * `CREATE_INITIAL_REVISION` with `REQUIRED_SOURCE_MISSING` instead of silently loading
	 * nothing. the mathematical domain declares its guide `required: false`, preserving today's
	 * silence exactly.
	 */
	readonly sources: readonly { readonly path: string; readonly required: boolean }[];
	/**
	 * The north (change 11 -- "a north a second domain can hold"): why a deliberation session
	 * exists and where it has to arrive. Structure stays the engine's (its shape, its presence
	 * in `STATUS`, its presence on the engine's two CLI-level error paths, all in `cli.mjs`);
	 * this is the domain's own text, sourced here exactly as `preservation`/`references` above
	 * source their own domain-specific behaviour instead of the engine hardcoding one domain's
	 * subject matter.
	 */
	readonly objective: {
		/** What this session is FOR -- not a good conversation, an artifact that exists and is current. */
		readonly purpose: string;
		/** Ordered. Every element states what it establishes and how a reader knows it is behind them. */
		readonly stages: readonly { readonly stage: string; readonly establishes: string; readonly behindWhen: string }[];
		/** Single-line literal: the Python arrival seal (`tests/test_agents.py`) reads this back out of a TypeScript-declared profile via an anchored regex. */
		readonly arrival: string;
		/** Optional: a session arriving mid-flow from outside this domain's own entry point, and the nearest stage to it. */
		readonly entrances?: readonly { readonly from: string; readonly arrivesAt: string; readonly note: string }[];
		/** What no operation may close on its own word -- always a person's decision. */
		readonly humanStops: readonly string[];
	};
};

const ARTIFACT_REQUIRED = ['directory', 'stem', 'revisionPattern', 'revisionLabel', 'sidecarRoot', 'marker'] as const;
const OBJECTIVE_REQUIRED = ['purpose', 'stages', 'arrival', 'humanStops'] as const;
// Finding M6: `REQUIRED` below only ever checked TOP-LEVEL key presence, so
// `vocabulary: {}` passed it exactly as vacuously as `artifact: {}` and `objective: {}`
// once did -- and unlike those two, nothing here ever caught it: a profile missing every
// one of these eight non-optional fields still started, then silently resolved no locus
// and blamed the caller's query for it.
const VOCABULARY_REQUIRED = ['conceptualTerms', 'expertPattern', 'displayNounPattern', 'displayNounStripPattern', 'subjectPattern', 'subjectTerms', 'subjectLocusDescription', 'subjectEvidenceLabel'] as const;
// `preservation: {}` / `references: {}` pass `REQUIRED` the same vacuous way; both fields
// are functions, never checked as more than "not undefined", so a profile missing either
// method started and died only at first use with "... is not a function".
const PRESERVATION_REQUIRED = ['extractAtoms', 'violations'] as const;
const REFERENCES_REQUIRED = ['declares', 'cites'] as const;
/** No `/`, no `..`, no empty segment -- a profile-supplied path segment escaping the workspace sandbox is the one adjacent risk change 3 introduces (design.md, "profile-supplied path segments are validated at load"). */
const SAFE_ARTIFACT_SEGMENT = /^\.?[A-Za-z0-9._-]+$/;
function isSafeArtifactSegment(value: unknown): value is string {
	return typeof value === 'string' && value.length > 0 && SAFE_ARTIFACT_SEGMENT.test(value) && !value.includes('..') && !value.includes('/');
}

const configured = process.env.DELIBERATION_DOMAIN_PROFILE;
if (!configured)
	throw new Error(
		"DELIBERATION_DOMAIN_PROFILE_REQUIRED: this engine serves no domain of its own. " +
		"Set DELIBERATION_DOMAIN_PROFILE to a module exporting `profile`, or launch " +
		"through a skill's own cli.mjs, which sets it.",
	);

// `proseReferenceText` is deliberately NOT here (finding L5): it is optional in the type
// above, since the engine itself never reads it and only one host's own preservation
// module needs it -- that host enforces its own requirement locally instead.
const REQUIRED = ["deriveBase", "baseLabel", "baseLabelLong", "exampleSlug", "names", "proseReferencePattern", "vocabulary", "artifact", "preservation", "references", "sources", "objective"] as const;

// Absolute, and refused otherwise. A relative path resolves against the working
// directory, and the engine does not control that: a CLI child process launched
// with its cwd inside the engine turned `skills/.../profile.ts` into
// `<engine>/skills/.../profile.ts` and died on a path nobody wrote. The
// launchers that set this variable all know an absolute path already.
if (!isAbsolute(configured))
	throw new Error(
		`DELIBERATION_DOMAIN_PROFILE_NOT_ABSOLUTE: ${configured} is relative, and the ` +
		"working directory a host or child process runs in is not the engine's to assume.",
	);

const loaded = (await import(configured)) as { profile?: DeliberationDomainProfile };
if (!loaded.profile) throw new Error(`DELIBERATION_DOMAIN_PROFILE_INVALID: ${configured} exports no \`profile\`.`);
const missing = REQUIRED.filter((key) => loaded.profile![key] === undefined);
if (missing.length) throw new Error(`DELIBERATION_DOMAIN_PROFILE_INCOMPLETE: ${configured} is missing ${missing.join(", ")}.`);

// `REQUIRED` above only ever checked top-level keys, so `artifact: {}` would have passed it
// vacuously. Every one of the six `artifact.*` fields is checked here explicitly -- still the
// same refusal code, naming the nested field instead of the top-level key.
const artifactValue = loaded.profile!.artifact as Record<string, unknown>;
const missingArtifact = ARTIFACT_REQUIRED.filter((key) => artifactValue[key] === undefined);
if (missingArtifact.length) throw new Error(`DELIBERATION_DOMAIN_PROFILE_INCOMPLETE: ${configured} is missing ${missingArtifact.map((key) => `artifact.${key}`).join(", ")}.`);

// `REQUIRED` above only ever checked top-level keys, so `objective: {}` would have passed it
// vacuously too -- the same bug `artifact: {}` already taught this file. Every one of the four
// `objective.*` fields is checked here explicitly, still under the same refusal code, naming
// the nested field instead of the top-level key.
const objectiveValue = loaded.profile!.objective as Record<string, unknown>;
const missingObjective = OBJECTIVE_REQUIRED.filter((key) => objectiveValue[key] === undefined);
if (missingObjective.length) throw new Error(`DELIBERATION_DOMAIN_PROFILE_INCOMPLETE: ${configured} is missing ${missingObjective.map((key) => `objective.${key}`).join(", ")}.`);

// `stages` presence alone (the check above) does not rule out `stages: []` -- a north with no
// stages is not a north. Every element must carry all three keys as non-empty strings, or a
// stage this domain declares by name would silently establish nothing and close on no
// condition at all. This used to test `=== undefined` only, which is the shape the guard was
// written for and not the harm: an `establishes` or `behindWhen` equal to the empty string
// is not `undefined` and slipped through, publishing an empty north field exactly as
// `humanStops: []` did below.
const nonEmptyString = (value: unknown): value is string => typeof value === 'string' && value.trim().length > 0;
const stages = objectiveValue.stages as readonly unknown[];
const stagesIncomplete = !Array.isArray(stages) || stages.length === 0
	|| stages.some((stage) => {
		const value = stage as Record<string, unknown>;
		return typeof value !== 'object' || value === null || !nonEmptyString(value.stage) || !nonEmptyString(value.establishes) || !nonEmptyString(value.behindWhen);
	});
if (stagesIncomplete) throw new Error(`DELIBERATION_DOMAIN_PROFILE_INCOMPLETE: ${configured} is missing objective.stages.`);

// `objective.arrival`/`objective.purpose` presence alone (`OBJECTIVE_REQUIRED` above) does
// not rule out `""` -- an empty string is not `undefined` and publishes an empty north field
// in every `STATUS` response and on both CLI error paths.
if (!nonEmptyString(objectiveValue.arrival) || !nonEmptyString(objectiveValue.purpose))
	throw new Error(`DELIBERATION_DOMAIN_PROFILE_INCOMPLETE: ${configured} is missing ${[!nonEmptyString(objectiveValue.arrival) ? 'objective.arrival' : undefined, !nonEmptyString(objectiveValue.purpose) ? 'objective.purpose' : undefined].filter(Boolean).join(", ")}.`);

// `objective.humanStops` presence alone does not rule out `[]` -- asserting that NOTHING is a
// person's decision is not a north either. `objective`'s own doc comment: "What no operation
// may close on its own word -- always a person's decision"; an empty array names none.
const humanStops = objectiveValue.humanStops as readonly unknown[];
if (!Array.isArray(humanStops) || humanStops.length === 0 || !humanStops.every(nonEmptyString))
	throw new Error(`DELIBERATION_DOMAIN_PROFILE_INCOMPLETE: ${configured} is missing objective.humanStops.`);

// `vocabulary: {}` passes `REQUIRED` exactly as vacuously as `artifact: {}` and `objective: {}`
// once did. All eight fields are checked here explicitly, under the same refusal code.
const vocabularyValue = loaded.profile!.vocabulary as Record<string, unknown>;
const missingVocabulary = VOCABULARY_REQUIRED.filter((key) => vocabularyValue[key] === undefined);
if (missingVocabulary.length) throw new Error(`DELIBERATION_DOMAIN_PROFILE_INCOMPLETE: ${configured} is missing ${missingVocabulary.map((key) => `vocabulary.${key}`).join(", ")}.`);

// `preservation: {}` / `references: {}` pass `REQUIRED` the same vacuous way. Both fields'
// members are functions the engine calls directly (`preservation.ts`, `candidate-validator.ts`,
// `reference-index.ts`, `document-index.ts`); a profile missing one used to start and die only
// at first use with a raw "... is not a function" instead of a clear refusal at load time.
const preservationValue = loaded.profile!.preservation as Record<string, unknown>;
const missingPreservation = PRESERVATION_REQUIRED.filter((key) => typeof preservationValue[key] !== 'function');
if (missingPreservation.length) throw new Error(`DELIBERATION_DOMAIN_PROFILE_INCOMPLETE: ${configured} is missing ${missingPreservation.map((key) => `preservation.${key}`).join(", ")}.`);

const referencesValue = loaded.profile!.references as Record<string, unknown>;
const missingReferences = REFERENCES_REQUIRED.filter((key) => typeof referencesValue[key] !== 'function');
if (missingReferences.length) throw new Error(`DELIBERATION_DOMAIN_PROFILE_INCOMPLETE: ${configured} is missing ${missingReferences.map((key) => `references.${key}`).join(", ")}.`);

// `sources` presence alone does not rule out `[]` or a list of malformed entries. Both shipped
// hosts declare at least one real source (one a single optional guide, the other three,
// two of them required) -- an empty or malformed list is indistinguishable from every
// `required: true` source check (`missingRequiredSources`, in the file that reads `sources`
// for fragment loading) silently never running, so it is refused rather than trusted.
const sourcesValue = loaded.profile!.sources;
const sourcesMalformed = !Array.isArray(sourcesValue) || sourcesValue.length === 0
	|| sourcesValue.some((source) => {
		const value = source as Record<string, unknown>;
		return typeof value !== 'object' || value === null || !nonEmptyString(value.path) || typeof value.required !== 'boolean';
	});
if (sourcesMalformed) throw new Error(`DELIBERATION_DOMAIN_PROFILE_INCOMPLETE: ${configured} declares an empty or malformed sources list.`);

// Change 3 turns a sandbox root (the managed directory, the sidecar root) into a profile value;
// `REQUIRED`-membership alone does not make a caller-supplied path segment safe to join under the
// project root. Both `directory` and `sidecarRoot` must be a single safe segment: no `/`, no `..`.
if (!isSafeArtifactSegment(artifactValue.directory) || !isSafeArtifactSegment(artifactValue.sidecarRoot))
	throw new Error(
		`DELIBERATION_DOMAIN_PROFILE_UNSAFE_ARTIFACT_PATH: ${configured} declares an unsafe artifact.directory or artifact.sidecarRoot ` +
		`(must match ${SAFE_ARTIFACT_SEGMENT.source}, and must not contain "/" or "..").`,
	);

/** The profile this process serves. Chosen by the host, never by the engine. */
export const DOMAIN: DeliberationDomainProfile = loaded.profile;

/** A fresh matcher for the domain's prose citations. Never shared: `matchAll` needs `g`, and a reused instance carries `lastIndex`. */
export const proseReference = (flags: string): RegExp => new RegExp(DOMAIN.proseReferencePattern, flags);
