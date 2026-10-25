import type { RevisionReceipt } from './types.js';
import type { ManagedRevisionName } from './artifact-naming.js';

export type InitialPublicationReceipt = {
	kind: 'INITIAL_PUBLICATION';
	/** The profile's own first-revision label (`artifact.revisionLabel(1)`), never the literal `'r01'`. */
	targetRevision: string;
	/** Was a fixed-stem-and-first-revision literal string type; see `revision-domain.ts`'s `CreateR01PayloadV1.target.filename` for why this is `ManagedRevisionName`, not plain `string`. */
	targetFilename: ManagedRevisionName;
	documentShaAfter: string;
	derivedStateStatus: 'COMMITTED';
	materializationId: string;
	selectionKey: string;
	planDigest: string;
	candidateDigest: string;
};

/**
 * Receipt for `InitialRevisionCreationService`'s explicit, slugged v1 creation (spec I1) --
 * distinct from `InitialPublicationReceipt`, which is reserved for the scientific workflow's
 * fixed-filename `CREATE_R01` contract (the bare-ROOT first revision only). `targetFilename` here is
 * the actual slugged filename (stem-lineage-first-revision). `kind` is intentionally omitted
 * (never `'INITIAL_PUBLICATION'`) so `derived-state-store.ts`'s `validatePublicationReceipt`
 * accepts it via its `kind===undefined` branch -- the same acceptance path an ordinary successor
 * `RevisionReceipt` uses.
 */
export type ManagedInitialRevisionReceipt = {
	operation: 'CREATE_INITIAL_REVISION';
	/** The profile's own first-revision label (`artifact.revisionLabel(1)`), never the literal `'r01'`. */
	targetRevision: string;
	targetFilename: string;
	documentShaAfter: string;
	derivedStateStatus: 'COMMITTED';
	createdAt: string;
	/** Present only on a first revision `ADOPT_INITIAL_REVISION` produced: the file it was adopted from (the revision's own name when an existing hand-adopted revision was recorded in place). Absent on every composed v1 and on every receipt before 0.14.0. */
	adoptedFrom?: string;
};

export type PublicationReceipt = RevisionReceipt | InitialPublicationReceipt;
export function createRevisionReceipt(receipt: PublicationReceipt) { return Object.freeze(receipt); }
