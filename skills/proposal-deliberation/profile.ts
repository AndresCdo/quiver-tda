import type { DeliberationDomainProfile } from "../_core/deliberation/engine/domain-profile.js";
import { extractAtoms, violations } from "./preservation-math.js";
import { declares, cites } from "./reference-math.js";

/**
 * What the shared deliberation engine needs to know about THIS domain.
 *
 * The engine under `_core/` is domain-neutral and refuses to start without one of
 * these. Everything here was once spelled inside the engine itself, which is why
 * a sibling skill could not reuse it without inheriting a research project it has
 * nothing to do with.
 */
export const profile: DeliberationDomainProfile = {
	deriveBase: "mathematical_proposal_base.md",
	baseLabel: "fixed proposal base",
	baseLabelLong: "fixed mathematical proposal base",
	// An invented example, never a real revision of a real project -- the same
	// shape `experimental-deliberation`'s own `exampleSlug` already has.
	exampleSlug: "kernel-aggregation-revisited-r06",
	// This domain owns no proper noun -- it is a general layer, and naming one
	// research project here is the exact coupling the profile mechanism removes.
	// The one word it names ITSELF by is its own namespace, which no file under
	// `_core/` spells, so the core-scan lock stays meaningful rather than vacuous.
	// Verbatim the reasoning its sibling already carries; the two are now
	// symmetric, and neither knows which paper it is serving.
	names: ["proposal-deliberation"],
	// These documents number with `\tag{N}` and cite as `(Ec. N)`; they do not
	// use `\label`/`\eqref`, so this is the only citation form that resolves.
	proseReferencePattern: "\\((?:Ec|Eq)\\.\\s*([0-9]+[a-z]?)\\)",
	proseReferenceText: (value) => `(Ec. ${value})`,
	vocabulary: {
		conceptualTerms: ["regularización", "motivación matemática", "múltiples dominios", "semi-supervisado"],
		expertPattern: "matem|ecuaci|regularización|semi-supervisado|teórico",
		displayNounPattern: "ecuaci[oó]n",
		displayNounStripPattern: "\\becuaci[oó]n(?:es)?\\b",
		subjectPattern: "one[- ]?hot|codificaci[oó]n|etiqueta|clase",
		subjectTerms: ["one-hot", "one hot"],
		subjectLocusDescription: "ecuación relacionada con one-hot",
		subjectEvidenceLabel: "nearby one-hot/coding definition",
		// Change 10: was a core-level unconditional literal in `intent-resolver.ts`. Opted in here,
		// with the exact same terms/label, so an instruction mentioning sparse/dispersed
		// representations keeps resolving to the exact same `requestedEffect` it always has --
		// this domain's own subject (regularisation, one-hot encoding) plausibly still needs it,
		// so the safer choice is preserving the signal explicitly rather than silently dropping it.
		requestedEffect: { terms: ["sparse", "dispers"], label: "representación sparse" },
	},
	// Exactly today's values: `directory`/`stem`/the `rNN` spelling/`sidecarRoot` (WITH its leading
	// dot)/`marker` were all previously hardcoded across core. This profile is now the only place
	// that names them, and core reads them back out through `artifact-naming.ts`.
	artifact: {
		directory: "proposals",
		stem: "research-concept",
		revisionPattern: "r",
		revisionLabel: (ordinal) => `r${String(ordinal).padStart(2, "0")}`,
		sidecarRoot: ".proposal-deliberation",
		marker: "<!-- proposal-workspace:artifact:v1 -->\n",
	},
	// The mathematical preservation gate (change 4): the atom extractor and canonical-form
	// rule set live in `preservation-math.ts`, wired through here so the shared core's
	// `preservation.ts` never hardcodes a single equation.
	preservation: { extractAtoms, violations },
	// Reference integrity (change 5): the declares/cites vocabulary lives in
	// `reference-math.ts`, wired through here so the shared core's `candidate-validator.ts`/
	// `reference-index.ts`/`document-index.ts` never hardcode `\label`/`\tag`/`\eqref`/`(Ec. N)`.
	references: { declares, cites },
	// Required sources (change 7): exactly today's single source, `guidance/paper-guide`,
	// declared NOT required -- an absent guide still renders v1 silently, identical to
	// pre-change behavior. A future source this domain cannot draft without would set
	// `required: true` instead.
	sources: [{ path: "guidance/paper-guide", required: false }],
	// The north (change 11): today's exact `OBJECTIVE_FLOW` text, byte-identical, moved
	// out of the engine and into this domain's own profile. This is the first change to
	// touch this file at all -- behaviour is unchanged, but the file has changed, which
	// `tests/proposal-deliberation-objective-flow.test.mjs` proves by deriving its
	// expectations from this profile rather than from a literal array of its own.
	objective: {
		purpose: "carry the mathematics that was discussed as far as a published managed revision -- not a good conversation, a document that exists and is the current one",
		stages: [
			{
				stage: "bound",
				establishes: "which revision is current and which entry of it the change touches",
				behindWhen: "`STATUS` named the latest and the target resolved to an entry",
			},
			{
				stage: "deliberated",
				establishes: "the change was argued through rather than typed",
				behindWhen: "THE USER SAID SO. Nothing here measures it, and nothing may: an agent that could close this stage on its own word would be approving its own proposal",
			},
			{
				stage: "composed",
				establishes: "the replacement exists written AS mathematics -- the equation, with its tag -- and not as a description of it",
				behindWhen: "a block exists carrying the equation and the tag it lands on",
			},
			{
				stage: "published",
				establishes: "the successor exists carrying the artifact marker and is the current revision",
				behindWhen: "this is the arrival; it is behind nobody",
			},
		],
		arrival: "the successor revision published and current, which is the only form the mathematics travels in",
		// This skill has an entrance from outside: a finding raised while
		// implementing arrives through a handoff, already near the composed stage.
		// Named because a session that entered there still owes the arrival, and a
		// finding that gets discussed, agreed, and never published is how this pair
		// of skills loses work.
		entrances: [
			{
				from: "a finding handed over by the implementation skill",
				arrivesAt: "composed",
				note: "it still owes publication; agreement is not arrival",
			},
		],
		humanStops: [
			"accepting the change, which closes the deliberated stage and which nothing here may close on its own",
			"authorizing publication, because it advances the real lineage",
		],
	},
};
