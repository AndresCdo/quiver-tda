import { constants } from 'node:fs';
import { access, lstat, mkdir, open, readFile, realpath, rm } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, join, resolve } from 'node:path';
import { deriveSlugFromTitle, InitialRevisionRenderer, type InitialRevisionGuideFragment } from './initial-revision-renderer.js';
import type { CanonicalProposalMetadata } from './revision-domain.js';
import { commitDerivedState, saveRevisionReceipt } from './derived-state-store.js';
import { rebuildDerivedState } from './derived-state-builder.js';
import { parseManagedRevisionFilename } from './revision-lifecycle-store.js';
import type { ManagedInitialRevisionReceipt } from './revision-receipt.js';
import { artifact, initialRevisionFilename, isInitialRevision, strictManagedRevision } from './artifact-naming.js';
import { violations as canonicalFormViolations } from './preservation.js';
import type { PreservationViolation } from './types.js';
import { initialCandidateRefusal, type CandidateValidationFailure } from './proposal-workspace.js';

export type { InitialRevisionGuideFragment };

const MANAGED_ARTIFACT_MARKER = artifact.marker;

function sha256(bytes: Buffer): string {
	return createHash('sha256').update(bytes).digest('hex');
}

/** Explicit v1 candidate produced from the caller's idea+guide (spec I1, I2, I5); never the fixed scientific-workflow `CreateR01PayloadV1` contract. */
export type InitialRevisionCandidate = {
	filename: string;
	/** The profile's own first-revision label (`artifact.revisionLabel(1)`), never a literal: the file is named by that label too, and a caller that read a fixed `'r01'` here got a label the document on disk does not carry. A TypeScript literal cannot depend on a runtime profile value, and this project runs no type checker at all, so the guard is a domain's own initial-revision test suite, never this annotation. */
	revision: string;
	markdown: string;
	canonicalMetadata: CanonicalProposalMetadata;
	/** `ADOPT_INITIAL_REVISION` only: the file this first revision was adopted from, recorded in its receipt. */
	adoptedFrom?: string;
};

/** Injectable seam (HARD test-isolation constraint): lets callers check "does a managed proposal already exist" without any real filesystem access. */
export type InitialRevisionExistingProposalPort = { hasManagedProposal(): Promise<boolean> };

export type InitialRevisionPublicationResult = { filename: string; revision: string; documentSha256: string; bytesWritten: number };

/** Injectable seam (HARD test-isolation constraint): lets tests capture the rendered candidate in memory instead of writing a real proposal `.md`. */
export type InitialRevisionPublicationPort = { publish(candidate: InitialRevisionCandidate): Promise<InitialRevisionPublicationResult> };

/** `dryRun`: run every check and the composition, then return before the creation lock and the write (`status: 'preview'`). */
export type CreateInitialRevisionInput = { idea: string; guideFragments?: readonly InitialRevisionGuideFragment[]; dryRun?: boolean };

export type CreateInitialRevisionResult =
	| { status: 'created'; filename: string; revision: string; documentSha256: string; canonicalMetadata: CanonicalProposalMetadata; markdown: string }
	| { status: 'preview'; filename: string; revision: string; canonicalMetadata: CanonicalProposalMetadata; markdown: string }
	| { status: 'blocked'; code: 'INITIAL_IDEA_REQUIRED' | 'MANAGED_PROPOSAL_ALREADY_EXISTS' | 'INITIAL_IDEA_SINGLE_SENTENCE' }
	| { status: 'blocked'; code: 'INITIAL_REVISION_CANONICAL_FORM_VIOLATION'; violations: readonly PreservationViolation[] }
	| { status: 'blocked'; code: 'INITIAL_REVISION_CANDIDATE_VALIDATION_FAILED'; candidateValidation: CandidateValidationFailure };

/**
 * The gate every first revision passes before a byte of it is written: this domain's canonical
 * form, then the structural pre-publish validation every successor's accept turn runs. One
 * function, so a composed v1 (`CREATE_INITIAL_REVISION`) and an adopted one
 * (`ADOPT_INITIAL_REVISION`) can never be held to two different standards.
 */
function initialRevisionGate(markdown: string):
	| { status: 'blocked'; code: 'INITIAL_REVISION_CANONICAL_FORM_VIOLATION'; violations: readonly PreservationViolation[] }
	| { status: 'blocked'; code: 'INITIAL_REVISION_CANDIDATE_VALIDATION_FAILED'; candidateValidation: CandidateValidationFailure }
	| undefined {
	const violations = canonicalFormViolations(markdown);
	if (violations.length) return { status: 'blocked', code: 'INITIAL_REVISION_CANONICAL_FORM_VIOLATION', violations };
	const candidateValidation = initialCandidateRefusal(markdown);
	if (candidateValidation) return { status: 'blocked', code: 'INITIAL_REVISION_CANDIDATE_VALIDATION_FAILED', candidateValidation };
	return undefined;
}

/**
 * Explicit, user-triggered creation of the first managed proposal (spec I1). Never auto-bootstraps:
 * it only ever runs when a caller explicitly invokes it, and it always refuses -- rather than
 * overwriting or duplicating -- whenever a managed proposal already exists. Composes
 * `InitialRevisionRenderer.renderFromIdea` (idea + paper-guide, never a fixed generic skeleton) and
 * delegates persistence to an injected publication port so the full creation logic (existence check,
 * rendering, refusal) is unit-testable without touching a real filesystem.
 */
export class InitialRevisionCreationService {
	constructor(
		private readonly existingProposal: InitialRevisionExistingProposalPort,
		private readonly publication: InitialRevisionPublicationPort,
		private readonly renderer: InitialRevisionRenderer = new InitialRevisionRenderer(),
	) {}

	async execute(input: CreateInitialRevisionInput): Promise<CreateInitialRevisionResult> {
		const idea = input.idea?.trim();
		if (!idea) return { status: 'blocked', code: 'INITIAL_IDEA_REQUIRED' };
		if (await this.existingProposal.hasManagedProposal()) return { status: 'blocked', code: 'MANAGED_PROPOSAL_ALREADY_EXISTS' };
		const composed = this.renderer.renderFromIdea({ idea, guideFragments: input.guideFragments });
		// An idea with no second sentence collapses `title` and `sectionHeading` to the same
		// bytes, by construction: `sectionHeading`'s fallback chain ends in `sentences[0] ?? idea`,
		// which is character for character what `title` computes on the line above it
		// (`initial-revision-renderer.ts`). The document then goes out with `# X` and `## X`
		// identical, and what that costs was measured on both hosts:
		//
		//   a domain with no canonical-form rules of its own  v1 IS created, and can never be
		//       edited: every locus query against it is ambiguous and blocked, and a second
		//       CREATE is refused MANAGED_PROPOSAL_ALREADY_EXISTS. The only exit is moving
		//       files by hand, outside this engine entirely.
		//   a domain that declares them  the renderer's triplication trips that domain's OWN
		//       canonical form, so an idea obeying every rule its skill states cannot become
		//       v1 at all -- and the refusal blames the author for a repetition THIS ENGINE
		//       introduced.
		//
		// Refused here rather than repaired in the renderer: this engine cannot write a section
		// heading the author did not write. `sentences` splits on `(?<=[.!?])\s+`, so "one
		// sentence" means "no sentence-ending punctuation" -- newlines and blank lines do not
		// supply one, which is why an idea laid out over several lines still collapses.
		if (composed.canonicalMetadata.title === composed.canonicalMetadata.sectionHeading) {
			return { status: 'blocked', code: 'INITIAL_IDEA_SINGLE_SENTENCE' };
		}
		// Canonical form, over the COMPOSED v1 rather than over the idea alone.
		//
		// Every other publication path in this engine runs `validateCandidate`, whose
		// `canonicalForm` term is exactly this rule set, before a byte is written. This one ran
		// nothing: `renderFromIdea` injects each declared source's fragment VERBATIM, so
		// whatever a source document happens to contain -- a report table already carrying
		// numbers, a URL nobody verified -- became v1 unexamined, and only a later successor
		// whose locus happened to cover that region would ever notice. For a domain whose whole
		// canonical form is "this document plans work that has not happened", that is the exact
		// failure the gate exists to prevent, and it is silent.
		//
		// `violations` and not `delta`: a violation is never an intentional change, so it
		// blocks outright rather than asking for an acknowledgement (`preservation.ts`). There
		// is nothing to acknowledge at v1 anyway -- no predecessor exists, so no atom can be
		// lost. A profile whose rule set recognizes nothing here returns `[]` and this is a
		// no-op, which is why the mathematical domain is unaffected.
		const gate = initialRevisionGate(composed.markdown);
		if (gate) return gate;
		// The first revision's pre-publish validation, the SAME set a guarded INITIAL_CREATE write
		// runs (size and reserved bytes, display blocks, standalone ATX headings). This path writes
		// through its own filesystem port and used to run none of it, so v1 could publish a line --
		// a heading fused with prose -- that every later successor's accept turn refuses over the
		// whole composed document, leaving no successor publishable until unrelated text was
		// reworded. Refusing it here gives v1, the successor preview and the accept turn one verdict.
		const filename = initialRevisionFilename(composed.slug);
		if (!isInitialRevision(filename)) throw new Error('INITIAL_REVISION_FILENAME_INVALID');
		const candidate: InitialRevisionCandidate = { filename, revision: artifact.revisionLabel(1), markdown: composed.markdown, canonicalMetadata: composed.canonicalMetadata };
		// The dry run ends here: every refusal above has run, and nothing below -- the creation
		// lock, the managed file, the state and the receipt -- is touched.
		if (input.dryRun === true) return { status: 'preview', filename: candidate.filename, revision: candidate.revision, canonicalMetadata: candidate.canonicalMetadata, markdown: candidate.markdown };
		let published: InitialRevisionPublicationResult;
		try {
			published = await this.publication.publish(candidate);
		} catch (error) {
			// Re-audit cleanup (issue #7): a concurrent winner (same OR a differently-slugged idea) may have
			// committed the project's single managed proposal between our pre-check above and this call's own
			// atomic publish attempt. Surface the same clean blocked result the pre-check itself would have
			// returned, instead of letting the raw error propagate uncaught.
			if (error instanceof Error && error.message === 'MANAGED_PROPOSAL_ALREADY_EXISTS') return { status: 'blocked', code: 'MANAGED_PROPOSAL_ALREADY_EXISTS' };
			throw error;
		}
		return { status: 'created', filename: published.filename, revision: published.revision, documentSha256: published.documentSha256, canonicalMetadata: candidate.canonicalMetadata, markdown: candidate.markdown };
	}
}

async function canonicalProposalsDirectory(projectRoot: string): Promise<string> {
	const root = await realpath(resolve(projectRoot));
	const directory = resolve(root, artifact.directory);
	let existing: string | undefined;
	try {
		existing = await realpath(directory);
	} catch {
		existing = undefined;
	}
	if (existing === undefined) {
		await mkdir(directory, { recursive: true, mode: 0o700 });
		existing = await realpath(directory);
	}
	if (existing !== directory) throw new Error('PROPOSALS_DIRECTORY_UNSAFE');
	const info = await lstat(directory);
	if (!info.isDirectory() || info.isSymbolicLink()) throw new Error('PROPOSALS_DIRECTORY_UNSAFE');
	return directory;
}

function initialRevisionLockPath(root: string): string {
	return join(root, artifact.sidecarRoot, 'locks', 'initial-revision.lock');
}

/** The creation lock's project-relative path, and whether it is on disk. Read-only: a dry run uses it to predict the refusal a real call would meet, and never creates or removes the lock. */
export async function initialRevisionLockState(projectRoot: string): Promise<{ path: string; present: boolean }> {
	const relative = join(artifact.sidecarRoot, 'locks', 'initial-revision.lock');
	try {
		await access(initialRevisionLockPath(projectRoot));
		return { path: relative, present: true };
	} catch {
		return { path: relative, present: false };
	}
}

/**
 * Re-audit cleanup (issue #7): a project-wide, slug-INDEPENDENT atomic single-winner guard.
 *
 * `hasManagedProposal`'s pre-check (in `proposal-workspace.ts`) and the target `.md`'s own O_EXCL
 * open (below) are each individually correct but not jointly sufficient: the pre-check is broad
 * (any managed file) but non-atomic with the write, while the O_EXCL write is atomic but keyed by
 * the exact SLUGGED filename. Two concurrent `CREATE_INITIAL_REVISION` calls with two DIFFERENT
 * ideas produce two different target filenames, so both could pass the pre-check and both O_EXCL
 * opens could succeed -- violating the single-managed-proposal invariant.
 *
 * This lock closes that gap: it is keyed by one FIXED path, independent of any slug, so only ONE
 * `open(..., O_EXCL)` on this exact path can ever succeed among any number of concurrent callers,
 * regardless of which idea (and therefore which target filename) each one carries. It is left in
 * place permanently on success -- mirroring the durable "a managed proposal now exists" invariant,
 * which is correctly permanent -- and released only when THIS attempt itself later fails, so a
 * legitimate retry after a failed write is never permanently locked out by our own failure.
 */
async function acquireInitialRevisionCreationLock(root: string): Promise<string> {
	const lockPath = initialRevisionLockPath(root);
	await mkdir(dirname(lockPath), { recursive: true, mode: 0o700 });
	let handle;
	try {
		handle = await open(lockPath, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | (constants.O_NOFOLLOW ?? 0), 0o600);
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code === 'EEXIST') throw new Error('MANAGED_PROPOSAL_ALREADY_EXISTS');
		throw error;
	}
	try {
		await handle.writeFile(Buffer.from(JSON.stringify({ createdAt: new Date().toISOString() })));
		await handle.sync();
	} finally {
		await handle.close();
	}
	return lockPath;
}

async function releaseInitialRevisionCreationLock(lockPath: string): Promise<void> {
	try {
		await rm(lockPath, { force: true });
	} catch {
		// Best-effort release only: a leftover lock after a failed attempt merely blocks the next retry,
		// it never corrupts or duplicates any managed proposal.
	}
}

/**
 * Real filesystem publication port used by production wiring; writes the marker-prefixed managed
 * `.md` atomically and only when the target does not already exist (guarded further by the
 * project-wide single-winner lock above), then writes the derived-state and receipt sidecars in
 * the SAME layout ordinary edit/materialization publication produces (`derived-state-store.ts`'s
 * profile-derived state/<filename>.json COMMITTED manifest and receipts/<filename>.json
 * receipt) -- re-audit cleanup (issue #2). Without these sidecars, `readCanonicalManagedRevisionInventory`
 * (`revision-lifecycle-store.ts`) hard-requires a COMMITTED state json and reports the whole inventory as
 * `inconsistent`, degrading scientific-workflow admission for an otherwise perfectly valid, freshly
 * created first revision.
 */
export function createFilesystemInitialRevisionPublicationPort(projectRoot: string): InitialRevisionPublicationPort {
	return {
		async publish(candidate) {
			const directory = await canonicalProposalsDirectory(projectRoot);
			const lockPath = await acquireInitialRevisionCreationLock(projectRoot);
			try {
				const target = resolve(directory, candidate.filename);
				if (dirname(target) !== directory) throw new Error('INITIAL_REVISION_TARGET_ESCAPES_PROPOSALS_DIRECTORY');
				const output = Buffer.concat([MANAGED_ARTIFACT_MARKER, Buffer.from(candidate.markdown, 'utf8')]);
				let handle;
				try {
					handle = await open(target, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | (constants.O_NOFOLLOW ?? 0), 0o600);
				} catch (error) {
					if ((error as NodeJS.ErrnoException).code === 'EEXIST') throw new Error('MANAGED_PROPOSAL_ALREADY_EXISTS');
					throw error;
				}
				try {
					await handle.writeFile(output);
					await handle.sync();
					const written = await handle.stat();
					if (!written.isFile() || written.nlink !== 1 || written.size !== output.length) throw new Error('INITIAL_REVISION_WRITE_VERIFICATION_FAILED');
				} finally {
					await handle.close();
				}
				const documentSha256 = sha256(output);
				const lineage = parseManagedRevisionFilename(candidate.filename).lineage;
				const derived = await rebuildDerivedState(candidate.filename, candidate.revision, lineage, output);
				await commitDerivedState(projectRoot, derived);
				const receipt: ManagedInitialRevisionReceipt = {
					operation: 'CREATE_INITIAL_REVISION',
					targetRevision: candidate.revision,
					targetFilename: candidate.filename,
					documentShaAfter: documentSha256,
					derivedStateStatus: 'COMMITTED',
					createdAt: new Date().toISOString(),
					...(candidate.adoptedFrom !== undefined ? { adoptedFrom: candidate.adoptedFrom } : {}),
				};
				await saveRevisionReceipt(projectRoot, candidate.filename, receipt);
				return { filename: candidate.filename, revision: candidate.revision, documentSha256, bytesWritten: output.length };
			} catch (error) {
				await releaseInitialRevisionCreationLock(lockPath);
				throw error;
			}
		},
	};
}

export type AdoptInitialRevisionResult =
	| { status: 'adopted'; mode: 'rename' | 'record'; sourceFilename: string; filename: string; revision: string; documentSha256: string }
	| { status: 'preview'; mode: 'rename' | 'record'; sourceFilename: string; filename: string; revision: string }
	| { status: 'blocked'; code: 'ADOPTION_SOURCE_INVALID' | 'ADOPTION_SOURCE_NOT_INITIAL' | 'ADOPTION_ALREADY_RECORDED' | 'MANAGED_PROPOSAL_ALREADY_EXISTS'; detail: string }
	| { status: 'blocked'; code: 'INITIAL_REVISION_CANONICAL_FORM_VIOLATION'; violations: readonly PreservationViolation[] }
	| { status: 'blocked'; code: 'INITIAL_REVISION_CANDIDATE_VALIDATION_FAILED'; candidateValidation: CandidateValidationFailure };

/** The first `# ` heading of a document, or undefined: the title an adopted revision is named after. */
function firstTitle(markdown: string): string | undefined {
	const match = /^# +(.+?)\s*#*\s*$/mu.exec(markdown);
	return match?.[1]?.trim() || undefined;
}

/**
 * `ADOPT_INITIAL_REVISION`: an EXISTING document becomes the first managed revision with exactly
 * what `CREATE_INITIAL_REVISION` gives a composed one -- the same gate (`initialRevisionGate`), the
 * same committed derived state, the same receipt shape (`operation: 'CREATE_INITIAL_REVISION'`,
 * plus an additive `adoptedFrom`) -- instead of the hand adoption both skills used to describe
 * (prepend the marker, rename the file), which left no state or receipt and ran no validation.
 *
 * Two modes, chosen by what `sourceFilename` names inside the managed directory:
 *
 *   rename  an unmanaged `.md` file. Refused while any managed revision exists. The document's
 *           own bytes (a leading artifact marker, if it already carries one, is dropped and
 *           re-added) go through the gate, then through the creation publication port itself --
 *           single-winner lock, exclusive write, state, receipt -- under
 *           `<stem>-<slug of its first "# " title, else of its filename>-<first label>.md`. The
 *           source is left in place, byte-identical: this engine never moves or deletes a file
 *           in the managed directory, so moving it to a backup stays the caller's confirmed act.
 *   record  a managed first revision already carrying the marker but holding NO receipt -- a
 *           revision adopted by hand before this operation existed. Its bytes are never touched;
 *           after the same gate, its committed state and receipt are written. The explicit
 *           repair path: a revision with a receipt is refused rather than re-recorded, and an
 *           unrecorded one that is never repaired keeps reading exactly as it always did. No lock
 *           is taken: a managed revision already exists, which is what the lock records.
 *
 * `dryRun` runs every check and returns before any write (`status: 'preview'`).
 */
export async function adoptInitialRevision(input: {
	projectRoot: string;
	sourceFilename: unknown;
	dryRun?: boolean;
	hasManagedProposal: () => Promise<boolean>;
	publication?: InitialRevisionPublicationPort;
}): Promise<AdoptInitialRevisionResult> {
	const name = input.sourceFilename;
	const invalid = (detail: string) => ({ status: 'blocked' as const, code: 'ADOPTION_SOURCE_INVALID' as const, detail });
	if (typeof name !== 'string' || !name || name !== name.trim() || name.includes('/') || name.includes('\\') || name.startsWith('.') || !name.endsWith('.md'))
		return invalid(`sourceFilename must name one Markdown file directly inside ${artifact.directory}/; got ${JSON.stringify(name)}.`);
	let root: string;
	let path: string;
	try {
		root = await realpath(resolve(input.projectRoot));
		path = join(root, artifact.directory, name);
		const info = await lstat(path);
		if (!info.isFile() || info.isSymbolicLink()) return invalid(`${artifact.directory}/${name} is not a regular file.`);
	} catch {
		return invalid(`${artifact.directory}/${name} does not exist.`);
	}
	const bytes = await readFile(path);
	const marked = bytes.subarray(0, MANAGED_ARTIFACT_MARKER.length).equals(MANAGED_ARTIFACT_MARKER);
	const markdown = (marked ? bytes.subarray(MANAGED_ARTIFACT_MARKER.length) : bytes).toString('utf8');
	if (!markdown.trim()) return invalid(`${artifact.directory}/${name} holds no content to adopt.`);
	const revision = artifact.revisionLabel(1);

	if (strictManagedRevision(name)) {
		if (!isInitialRevision(name) || !marked)
			return { status: 'blocked', code: 'ADOPTION_SOURCE_NOT_INITIAL', detail: `${name} is ${marked ? 'a managed revision past the first' : 'named like a managed revision but carries no artifact marker'}; only a first revision can be adopted in place, and only an unmanaged file can become one.` };
		try {
			await access(join(root, artifact.sidecarRoot, 'receipts', `${name}.json`));
			return { status: 'blocked', code: 'ADOPTION_ALREADY_RECORDED', detail: `${name} already has a receipt (${artifact.sidecarRoot}/receipts/${name}.json); it is never re-recorded or replaced.` };
		} catch {
			// No receipt: the revision this mode exists for.
		}
		const gate = initialRevisionGate(markdown);
		if (gate) return gate;
		if (input.dryRun === true) return { status: 'preview', mode: 'record', sourceFilename: name, filename: name, revision };
		const documentSha256 = sha256(bytes);
		const lineage = parseManagedRevisionFilename(name).lineage;
		await commitDerivedState(root, await rebuildDerivedState(name, revision, lineage, bytes));
		const receipt: ManagedInitialRevisionReceipt = { operation: 'CREATE_INITIAL_REVISION', targetRevision: revision, targetFilename: name, documentShaAfter: documentSha256, derivedStateStatus: 'COMMITTED', createdAt: new Date().toISOString(), adoptedFrom: name };
		await saveRevisionReceipt(root, name, receipt);
		return { status: 'adopted', mode: 'record', sourceFilename: name, filename: name, revision, documentSha256 };
	}

	if (await input.hasManagedProposal())
		return { status: 'blocked', code: 'MANAGED_PROPOSAL_ALREADY_EXISTS', detail: 'A managed revision already exists; adoption creates the first one and never a second lineage beside it.' };
	const gate = initialRevisionGate(markdown);
	if (gate) return gate;
	const slug = deriveSlugFromTitle(firstTitle(markdown) ?? name.slice(0, -'.md'.length));
	const filename = initialRevisionFilename(slug);
	if (!isInitialRevision(filename)) throw new Error('INITIAL_REVISION_FILENAME_INVALID');
	if (input.dryRun === true) return { status: 'preview', mode: 'rename', sourceFilename: name, filename, revision };
	const publication = input.publication ?? createFilesystemInitialRevisionPublicationPort(root);
	try {
		const published = await publication.publish({ filename, revision, markdown, canonicalMetadata: { schemaVersion: 1, title: firstTitle(markdown) ?? slug, sectionHeading: /^## +(.+?)\s*$/mu.exec(markdown)?.[1] ?? firstTitle(markdown) ?? slug }, adoptedFrom: name });
		return { status: 'adopted', mode: 'rename', sourceFilename: name, filename: published.filename, revision: published.revision, documentSha256: published.documentSha256 };
	} catch (error) {
		if (error instanceof Error && error.message === 'MANAGED_PROPOSAL_ALREADY_EXISTS')
			return { status: 'blocked', code: 'MANAGED_PROPOSAL_ALREADY_EXISTS', detail: `The creation lock ${join(artifact.sidecarRoot, 'locks', 'initial-revision.lock')} or the target ${filename} already exists; a first revision was already created here.` };
		throw error;
	}
}
