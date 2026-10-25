import { createHash, randomUUID } from 'node:crypto';
import { constants } from 'node:fs';
import { lstat, mkdir, open, readFile, realpath } from 'node:fs/promises';
import { basename, dirname, extname, isAbsolute, normalize, relative, resolve, sep } from 'node:path';
import { writeTask } from './runtime-metrics.js';
import { resolveLatestManagedRevision } from './revision-lifecycle-store.js';
import { documentPath } from './artifact-naming.js';

const DEFAULT_DRAFT_DIRECTORY = 'drafts';
const DEFAULT_ALLOWED_EXTENSIONS = ['.md'] as const;
const MAX_DRAFT_BYTES = 256 * 1024;
// Finding M7: this file used to also declare a hardcoded
// `MANAGED_ARTIFACT_MARKER = Buffer.from('<!-- proposal-workspace:artifact:v1 -->\n')`
// here. Unlike `patch-compiler.ts`'s copy, this one had zero readers anywhere in the
// file -- dead from the moment it was written, not merely wrong for a domain that
// changed its marker. Deleted rather than rewired to `artifact.marker`, since wiring a
// value nothing reads would still leave a declaration with no reason to exist.
const SAFE_METADATA_PART = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;

export type DraftDocumentMetadata = {
	slug?: string;
	purpose?: string;
	revision?: string;
	extension?: string;
};

export type DraftNamingInput = Required<Pick<DraftDocumentMetadata, 'slug' | 'purpose' | 'extension'>> & Pick<DraftDocumentMetadata, 'revision'>;
export type DraftNamingStrategy = (metadata: DraftNamingInput) => string;
export type ManagedDocumentInventoryEntry = { path: string; revision?: string; modifiedMs?: number };
export type ManagedDocumentInventory = (projectRoot: string) => Promise<readonly ManagedDocumentInventoryEntry[]>;

export type DraftMaterializationPolicy = {
	draftDirectory?: string;
	allowedExtensions?: readonly string[];
	managedDocumentPath?: string;
	managedDocumentInventory?: ManagedDocumentInventory;
	namingStrategy?: DraftNamingStrategy;
	documentMetadata?: DraftDocumentMetadata;
};

export type DraftMaterializationRequest = {
	operation: 'INITIAL_CREATE' | 'UPDATE' | 'REPLACE';
	route?: string;
	approveProposedRoute?: boolean;
	authorized: boolean;
	metadata?: DraftDocumentMetadata;
};

/** Immutable content handoff created by CHAT_DELIBERATION and consumed by DOCUMENT_EDIT. */
export type DraftMaterializationPayload = Readonly<{
	source: 'CHAT_DELIBERATION';
	conversationId: string;
	content: string;
}>;

type GuardReceipt = { decision: 'allowed' | 'denied'; authorization?: string; reason?: { code?: string } };
type DraftOperationGuard = {
	execute(input: {
		action: 'begin_document_operation' | 'preflight_plan' | 'authorize_mutation' | 'complete_operation' | 'block_operation';
		operation_id: string;
		mode?: 'INITIAL_CREATE';
		budget?: { max_document_delegations: number; attempts: number; model_candidates: number; patches: number };
		targetFilename?: string;
		mutationAction?: 'create_draft';
		userAuthorized?: boolean;
		reason?: string;
	}): Promise<GuardReceipt>;
};

export type DraftMaterializationResult = {
	status: 'draft_path_proposed' | 'materialized' | 'blocked';
	operation: 'INITIAL_CREATE' | 'UPDATE' | 'REPLACE';
	route: string | null;
	requestedRoute?: string;
	bytesWritten: number;
	primaryDocumentPath: string | null;
	primaryDocumentIntact: boolean;
	terminalState: 'PENDING_APPROVAL' | 'COMPLETED' | 'BLOCKED';
	nextAction: 'approve_proposed_route' | null;
	mutations: 0 | 1;
	reason?: string;
	missingPayload?: 'materializationPayload';
};

type ResolvedPolicy = {
	draftDirectory: string;
	allowedExtensions: readonly string[];
	managedDocumentPath?: string;
	managedDocumentInventory: ManagedDocumentInventory;
	namingStrategy: DraftNamingStrategy;
	documentMetadata: DraftDocumentMetadata;
};

type PrimaryDocument = { route: string; realPath: string; bytes: Buffer; sha256: string; metadata: DraftDocumentMetadata };

function sha256(bytes: Buffer): string {
	return createHash('sha256').update(bytes).digest('hex');
}

function isInside(parent: string, candidate: string): boolean {
	const child = relative(parent, candidate);
	return child === '' || (!child.startsWith(`..${sep}`) && child !== '..' && !isAbsolute(child));
}

function validateRelativeRoute(value: string, label: string): string {
	if (!value || value.includes('\0') || value.includes('\\') || isAbsolute(value)) throw new Error(`${label}_ABSOLUTE_OR_INVALID`);
	const segments = value.split('/');
	if (segments.some(segment => segment === '' || segment === '.' || segment === '..')) throw new Error(`${label}_NOT_NORMALIZED`);
	if (normalize(value) !== value) throw new Error(`${label}_NOT_NORMALIZED`);
	return value;
}

function normalizeExtension(value: string): string {
	const extension = value.toLowerCase();
	if (!/^\.[a-z0-9]{1,10}$/.test(extension)) throw new Error('DRAFT_EXTENSION_POLICY_INVALID');
	return extension;
}

function metadataPart(value: string | undefined, fallback: string): string {
	const normalized = (value ?? fallback).trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
	if (!normalized || !SAFE_METADATA_PART.test(normalized)) throw new Error('DRAFT_METADATA_INVALID');
	return normalized;
}

export function defaultDraftNamingStrategy(metadata: DraftNamingInput): string {
	return [metadata.slug, metadata.purpose, metadata.revision].filter(Boolean).join('-') + metadata.extension;
}

/**
 * Delegates enumeration to the unified `resolveLatestManagedRevision` (design decision I3/I4)
 * instead of this module's own mtime-based tie-break, so the default draft-naming base agrees
 * exactly with every other "latest managed revision" call site. Returns at most the one canonical
 * winner; `resolvePrimaryDocument`'s own generic sort below then becomes a no-op for this default.
 */
async function defaultManagedDocumentInventory(projectRoot: string): Promise<readonly ManagedDocumentInventoryEntry[]> {
	const resolution = await resolveLatestManagedRevision(projectRoot, { markerOwned: true }).catch(() => undefined);
	if (!resolution || resolution.status === 'empty') return [];
	return [{ path: documentPath(resolution.latest.filename), revision: String(resolution.latest.revisionNumber) }];
}

function resolvePolicy(policy: DraftMaterializationPolicy): ResolvedPolicy {
	const draftDirectory = validateRelativeRoute((policy.draftDirectory ?? DEFAULT_DRAFT_DIRECTORY).replace(/\/$/, ''), 'DRAFT_DIRECTORY');
	const allowedExtensions = [...new Set((policy.allowedExtensions ?? DEFAULT_ALLOWED_EXTENSIONS).map(normalizeExtension))];
	if (allowedExtensions.length === 0) throw new Error('DRAFT_EXTENSION_POLICY_EMPTY');
	return {
		draftDirectory,
		allowedExtensions,
		managedDocumentPath: policy.managedDocumentPath,
		managedDocumentInventory: policy.managedDocumentInventory ?? defaultManagedDocumentInventory,
		namingStrategy: policy.namingStrategy ?? defaultDraftNamingStrategy,
		documentMetadata: policy.documentMetadata ?? {},
	};
}

async function safeRegularFile(root: string, route: string, label: string): Promise<{ route: string; realPath: string; bytes: Buffer }> {
	const normalized = validateRelativeRoute(route, label);
	const lexical = resolve(root, normalized);
	if (!isInside(root, lexical)) throw new Error(`${label}_ESCAPES_PROJECT`);
	const entry = await lstat(lexical);
	if (entry.isSymbolicLink() || !entry.isFile() || entry.nlink !== 1) throw new Error(`${label}_NOT_REGULAR`);
	const canonical = await realpath(lexical);
	if (!isInside(root, canonical) || canonical !== lexical) throw new Error(`${label}_SYMLINK_OR_ESCAPE`);
	return { route: normalized, realPath: canonical, bytes: await readFile(canonical) };
}

async function resolvePrimaryDocument(projectRoot: string, policy: ResolvedPolicy): Promise<PrimaryDocument> {
	const root = await realpath(projectRoot);
	let route = policy.managedDocumentPath;
	if (!route) {
		const inventory = await policy.managedDocumentInventory(root);
		const sorted = [...inventory].sort((left, right) => {
			const revisionDelta = Number(left.revision ?? -1) - Number(right.revision ?? -1);
			return revisionDelta || Number(left.modifiedMs ?? 0) - Number(right.modifiedMs ?? 0) || left.path.localeCompare(right.path);
		});
		route = sorted.at(-1)?.path;
	}
	if (!route) throw new Error('MANAGED_DOCUMENT_PATH_UNRESOLVED');
	const primary = await safeRegularFile(root, route, 'MANAGED_DOCUMENT_PATH');
	const stem = basename(primary.route, extname(primary.route));
	const revisionMatch = stem.match(/(?:^|-)r(\d+)$/i);
	const slug = revisionMatch ? stem.slice(0, revisionMatch.index).replace(/-$/, '') : stem;
	return {
		...primary,
		sha256: sha256(primary.bytes),
		metadata: { slug: metadataPart(slug, 'document'), ...(revisionMatch ? { revision: `r${revisionMatch[1]}` } : {}) },
	};
}

async function ensureDraftDirectory(root: string, configured: string, create: boolean): Promise<string> {
	const lexical = resolve(root, configured);
	if (!isInside(root, lexical)) throw new Error('DRAFT_DIRECTORY_ESCAPES_PROJECT');
	const segments = configured.split('/');
	let cursor = root;
	for (let index = 0; index < segments.length; index += 1) {
		cursor = resolve(cursor, segments[index]);
		try {
			const entry = await lstat(cursor);
			if (entry.isSymbolicLink() || !entry.isDirectory()) throw new Error('DRAFT_DIRECTORY_SYMLINK_OR_INVALID');
		} catch (error) {
			if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
			if (!create) return lexical;
			await mkdir(cursor, { mode: 0o700 });
		}
	}
	const canonical = await realpath(lexical);
	if (canonical !== lexical || !isInside(root, canonical)) throw new Error('DRAFT_DIRECTORY_SYMLINK_OR_ESCAPE');
	return canonical;
}

function generatedRoute(primary: PrimaryDocument, policy: ResolvedPolicy, metadata: DraftDocumentMetadata): string {
	const combined = { ...primary.metadata, ...policy.documentMetadata, ...metadata };
	const extension = normalizeExtension(combined.extension ?? (extname(primary.route) || policy.allowedExtensions[0]));
	if (!policy.allowedExtensions.includes(extension)) throw new Error('DRAFT_EXTENSION_NOT_ALLOWED');
	const filename = policy.namingStrategy({
		slug: metadataPart(combined.slug, 'document'),
		purpose: metadataPart(combined.purpose, 'draft'),
		...(combined.revision ? { revision: metadataPart(combined.revision, '') } : {}),
		extension,
	});
	if (basename(filename) !== filename) throw new Error('DRAFT_NAMING_STRATEGY_RETURNED_PATH');
	validateRelativeRoute(filename, 'DRAFT_FILENAME');
	return `${policy.draftDirectory}/${filename}`;
}

async function validateDraftTarget(root: string, route: string, primary: PrimaryDocument, policy: ResolvedPolicy, createDirectory: boolean): Promise<string> {
	const exactRoute = validateRelativeRoute(route, 'DRAFT_ROUTE');
	if (!exactRoute.startsWith(`${policy.draftDirectory}/`)) throw new Error('DRAFT_ROUTE_OUTSIDE_DIRECTORY');
	const extension = extname(exactRoute).toLowerCase();
	if (!policy.allowedExtensions.includes(extension)) throw new Error('DRAFT_EXTENSION_NOT_ALLOWED');
	const draftDirectory = await ensureDraftDirectory(root, policy.draftDirectory, createDirectory);
	const target = resolve(root, exactRoute);
	if (!isInside(root, target) || target === primary.realPath) throw new Error(target === primary.realPath ? 'DRAFT_ROUTE_IS_PRIMARY_DOCUMENT' : 'DRAFT_ROUTE_OUTSIDE_DIRECTORY');
	try {
		await lstat(target);
		throw new Error('DRAFT_TARGET_ALREADY_EXISTS');
	} catch (error) {
		if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
	}
	const parent = dirname(target);
	let canonicalParent: string;
	try {
		canonicalParent = await realpath(parent);
	} catch (error) {
		if (!createDirectory && parent === draftDirectory && (error as NodeJS.ErrnoException).code === 'ENOENT') return target;
		throw new Error('DRAFT_PARENT_DIRECTORY_NOT_FOUND');
	}
	if (!isInside(draftDirectory, canonicalParent) || resolve(canonicalParent, basename(target)) !== target) throw new Error('DRAFT_ROUTE_SYMLINK_OR_ESCAPE');
	return target;
}

async function verifyPrimary(primary: PrimaryDocument): Promise<boolean> {
	try {
		const entry = await lstat(primary.realPath);
		if (entry.isSymbolicLink() || !entry.isFile() || entry.nlink !== 1 || (await realpath(primary.realPath)) !== primary.realPath) return false;
		return sha256(await readFile(primary.realPath)) === primary.sha256;
	} catch {
		return false;
	}
}

function requireAllowed(receipt: GuardReceipt, step: string): GuardReceipt {
	if (receipt.decision !== 'allowed') throw new Error(`DRAFT_GUARD_${step}_${receipt.reason?.code ?? 'DENIED'}`);
	return receipt;
}

/** Explicit, create-only transition from session-local chat content to one protected draft route. */
export class DraftMaterializationService {
	private readonly policy: ResolvedPolicy;
	private readonly pendingRoutes = new Map<string, string>();

	constructor(private readonly projectRoot: string, private readonly guard: DraftOperationGuard, policy: DraftMaterializationPolicy = {}, private readonly operationIdFactory: () => string = () => `deliberation-draft-`) {
		this.policy = resolvePolicy(policy);
	}

	async execute(input: { conversationId: string; materializationPayload?: DraftMaterializationPayload; request: DraftMaterializationRequest }): Promise<DraftMaterializationResult> {
		const requestedRoute = input.request.route;
		let primary: PrimaryDocument | undefined;
		let route: string | null = requestedRoute ?? null;
		let operationId: string | undefined;
		let guardActive = false;
		try {
			if (input.request.operation !== 'INITIAL_CREATE') throw new Error('CHAT_DRAFT_UPDATE_REPLACE_FORBIDDEN');
			if (!input.materializationPayload?.content.trim()) throw new Error('CHAT_CONTENT_REQUIRED');
			if (input.materializationPayload.source !== 'CHAT_DELIBERATION') throw new Error('CHAT_MATERIALIZATION_PAYLOAD_INVALID');
			if (input.materializationPayload.conversationId !== input.conversationId) throw new Error('CHAT_MATERIALIZATION_PAYLOAD_CONVERSATION_MISMATCH');
			if (!input.conversationId.startsWith('chat-')) throw new Error('CHAT_CONVERSATION_ID_INVALID');
			const content = input.materializationPayload.content;
			primary = await resolvePrimaryDocument(this.projectRoot, this.policy);
			if (!route) {
				if (input.request.approveProposedRoute) {
					route = this.pendingRoutes.get(input.conversationId) ?? null;
					if (!route) throw new Error('DRAFT_ROUTE_APPROVAL_NOT_PENDING');
				} else {
					route = generatedRoute(primary, this.policy, input.request.metadata ?? {});
					await validateDraftTarget(await realpath(this.projectRoot), route, primary, this.policy, false);
					this.pendingRoutes.set(input.conversationId, route);
					return { status: 'draft_path_proposed', operation: 'INITIAL_CREATE', route, bytesWritten: 0, primaryDocumentPath: primary.route, primaryDocumentIntact: await verifyPrimary(primary), terminalState: 'PENDING_APPROVAL', nextAction: 'approve_proposed_route', mutations: 0 };
				}
			}
			if (!input.request.authorized) throw new Error('INITIAL_CREATE_NOT_AUTHORIZED_CURRENT_TURN');
			const root = await realpath(this.projectRoot);
			const target = await validateDraftTarget(root, route, primary, this.policy, true);
			const output = Buffer.from(content, 'utf8');
			if (output.length === 0 || output.length > MAX_DRAFT_BYTES || content.includes('\0')) throw new Error('DRAFT_CONTENT_INVALID');
			operationId = this.operationIdFactory();
			requireAllowed(await this.guard.execute({ action: 'begin_document_operation', operation_id: operationId }), 'BEGIN');
			guardActive = true;
			requireAllowed(await this.guard.execute({ action: 'preflight_plan', operation_id: operationId, mode: 'INITIAL_CREATE', budget: { max_document_delegations: 0, attempts: 1, model_candidates: 0, patches: 0 }, targetFilename: route, mutationAction: 'create_draft', userAuthorized: true }), 'PREFLIGHT');
			const authorization = requireAllowed(await this.guard.execute({ action: 'authorize_mutation', operation_id: operationId }), 'AUTHORIZE');
			if (!authorization.authorization) throw new Error('DRAFT_MUTATION_AUTHORIZATION_MISSING');
			await writeTask(async () => {
				const handle = await open(target, constants.O_WRONLY | constants.O_CREAT | constants.O_EXCL | (constants.O_NOFOLLOW ?? 0), 0o600);
				try {
					await handle.writeFile(output);
					await handle.sync();
					const written = await handle.stat();
					if (!written.isFile() || written.nlink !== 1 || written.size !== output.length) throw new Error('DRAFT_WRITE_VERIFICATION_FAILED');
				} finally {
					await handle.close();
				}
			});
			if (!await verifyPrimary(primary)) throw new Error('PRIMARY_DOCUMENT_CHANGED_DURING_DRAFT_CREATE');
			requireAllowed(await this.guard.execute({ action: 'complete_operation', operation_id: operationId }), 'COMPLETE');
			guardActive = false;
			this.pendingRoutes.delete(input.conversationId);
			return { status: 'materialized', operation: 'INITIAL_CREATE', route, bytesWritten: output.length, primaryDocumentPath: primary.route, primaryDocumentIntact: true, terminalState: 'COMPLETED', nextAction: null, mutations: 1 };
		} catch (error) {
			const reason = error instanceof Error ? error.message : String(error);
			if (guardActive && operationId) {
				try { await this.guard.execute({ action: 'block_operation', operation_id: operationId, reason }); } catch {}
			}
			return { status: 'blocked', operation: input.request.operation, route, ...(requestedRoute !== undefined ? { requestedRoute } : {}), bytesWritten: 0, primaryDocumentPath: primary?.route ?? null, primaryDocumentIntact: primary ? await verifyPrimary(primary) : false, terminalState: 'BLOCKED', nextAction: null, mutations: 0, reason, ...(reason === 'CHAT_CONTENT_REQUIRED' ? { missingPayload: 'materializationPayload' as const } : {}) };
		}
	}
}
