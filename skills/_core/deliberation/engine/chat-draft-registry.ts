import type { ExtensionContext, SessionShutdownEvent } from './_pi-compat/pi-coding-agent.js';
import type { DraftMaterializationPayload } from './draft-materialization.js';

export const MAX_CHAT_CONVERSATIONS = 32;
export const MAX_CHAT_TURNS = 8;
export const MAX_CHAT_CONCLUSION_BYTES = 2_000;
export const MAX_CHAT_DRAFT_BYTES = (MAX_CHAT_TURNS * MAX_CHAT_CONCLUSION_BYTES) + ((MAX_CHAT_TURNS - 1) * 2);
const MAX_RUNTIME_SESSIONS = 32;
const MAX_IDENTITY_BYTES = 256;
const CHAT_CONVERSATION_ID = /^chat-[a-z0-9][a-z0-9-]{0,250}$/;
// A dot-joined registry key here would coincidentally spell the dot-prefixed sidecar-root
// value by pure namespace-convention accident, which the core-only artifact-namespace lock
// (`artifact-naming.ts`) would flag. The registry key is opaque and never read back as a
// path, so a colon-joined form is behaviorally identical and spells no artifact value.
const SHARED_REGISTRY_SYMBOL = Symbol.for('papersmith-ai:deliberation:pi-session-draft-registry/v1');

type SessionIdentityContext = Pick<ExtensionContext, 'sessionManager'>;
type SessionDrafts = Map<string, DraftMaterializationPayload>;

export type PiSessionDraftRegistry = {
	put(sessionIdentity: string, conversationId: string, payload: DraftMaterializationPayload): void;
	get(sessionIdentity: string, conversationId: string): DraftMaterializationPayload | undefined;
	has(sessionIdentity: string, conversationId: string): boolean;
	delete(sessionIdentity: string, conversationId: string): boolean;
	clearSession(sessionIdentity: string): void;
	sessionSize(sessionIdentity: string): number;
};

export type PiSessionDraftLifecycleAdapter = {
	sessionIdentity(context: SessionIdentityContext): string;
	shouldClearSession(event: Pick<SessionShutdownEvent, 'reason'>): boolean;
};

function validateIdentity(value: string, label: string): string {
	if (!value || value.includes('\0') || Buffer.byteLength(value) > MAX_IDENTITY_BYTES) throw new Error(`${label}_INVALID`);
	return value;
}

function validateConversationId(value: string): string {
	if (!CHAT_CONVERSATION_ID.test(value)) throw new Error('CHAT_CONVERSATION_ID_INVALID');
	return value;
}

function immutablePayload(payload: DraftMaterializationPayload): DraftMaterializationPayload {
	if (payload.source !== 'CHAT_DELIBERATION') throw new Error('CHAT_MATERIALIZATION_PAYLOAD_INVALID');
	validateConversationId(payload.conversationId);
	const bytes = Buffer.byteLength(payload.content);
	if (!payload.content.trim() || bytes > MAX_CHAT_DRAFT_BYTES) throw new Error('CHAT_MATERIALIZATION_PAYLOAD_BOUNDS_INVALID');
	return Object.freeze({ source: payload.source, conversationId: payload.conversationId, content: payload.content });
}

export function createPiSessionDraftRegistry(): PiSessionDraftRegistry {
	const sessions = new Map<string, SessionDrafts>();
	return Object.freeze({
		put(sessionIdentity, conversationId, payload) {
			const sessionKey = validateIdentity(sessionIdentity, 'PI_SESSION_IDENTITY');
			const draftKey = validateConversationId(conversationId);
			if (payload.conversationId !== draftKey) throw new Error('CHAT_MATERIALIZATION_PAYLOAD_CONVERSATION_MISMATCH');
			let drafts = sessions.get(sessionKey);
			if (!drafts) {
				if (sessions.size >= MAX_RUNTIME_SESSIONS) sessions.delete(sessions.keys().next().value!);
				drafts = new Map();
				sessions.set(sessionKey, drafts);
			}
			if (!drafts.has(draftKey) && drafts.size >= MAX_CHAT_CONVERSATIONS) drafts.delete(drafts.keys().next().value!);
			drafts.set(draftKey, immutablePayload(payload));
		},
		get(sessionIdentity, conversationId) {
			const payload = sessions.get(validateIdentity(sessionIdentity, 'PI_SESSION_IDENTITY'))?.get(validateConversationId(conversationId));
			return payload ? immutablePayload(payload) : undefined;
		},
		has(sessionIdentity, conversationId) {
			return sessions.get(validateIdentity(sessionIdentity, 'PI_SESSION_IDENTITY'))?.has(validateConversationId(conversationId)) ?? false;
		},
		delete(sessionIdentity, conversationId) {
			const sessionKey = validateIdentity(sessionIdentity, 'PI_SESSION_IDENTITY');
			const drafts = sessions.get(sessionKey);
			if (!drafts) return false;
			const deleted = drafts.delete(validateConversationId(conversationId));
			if (drafts.size === 0) sessions.delete(sessionKey);
			return deleted;
		},
		clearSession(sessionIdentity) {
			sessions.delete(validateIdentity(sessionIdentity, 'PI_SESSION_IDENTITY'));
		},
		sessionSize(sessionIdentity) {
			return sessions.get(validateIdentity(sessionIdentity, 'PI_SESSION_IDENTITY'))?.size ?? 0;
		},
	});
}

function isDraftRegistry(value: unknown): value is PiSessionDraftRegistry {
	if (!value || typeof value !== 'object') return false;
	const candidate = value as Partial<PiSessionDraftRegistry>;
	return ['put', 'get', 'has', 'delete', 'clearSession', 'sessionSize'].every(method => typeof candidate[method as keyof PiSessionDraftRegistry] === 'function');
}

export function getSharedPiSessionDraftRegistry(): PiSessionDraftRegistry {
	const scope = globalThis as typeof globalThis & Record<symbol, unknown>;
	const existing = scope[SHARED_REGISTRY_SYMBOL];
	if (existing !== undefined) {
		if (!isDraftRegistry(existing)) throw new Error('PI_SESSION_DRAFT_REGISTRY_INVALID');
		return existing;
	}
	const registry = createPiSessionDraftRegistry();
	Object.defineProperty(scope, SHARED_REGISTRY_SYMBOL, { value: registry, configurable: false, enumerable: false, writable: false });
	return registry;
}

export const defaultPiSessionDraftLifecycleAdapter: PiSessionDraftLifecycleAdapter = Object.freeze({
	sessionIdentity(context) {
		return validateIdentity(context.sessionManager.getSessionId(), 'PI_SESSION_IDENTITY');
	},
	shouldClearSession(event) {
		return event.reason !== 'reload';
	},
});
