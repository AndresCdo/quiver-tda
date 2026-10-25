import { randomBytes } from 'node:crypto';
import type { Compilation, EditAction, EditPlan } from './types.js';

const MAX_SESSIONS = 32;
const MAX_PREVIEWS_PER_SESSION = 8;
const TOKEN = /^[A-Za-z0-9_-]{32,128}$/;

export type FrozenSuccessorPreview = Readonly<{
 sourceFilename: string;
 sourceRevision: string;
 sourceSha256: string;
 /** One or more resolved composite locus ids (design amendment: multi-section successor), in resolution order. */
 compositeTargetIds: readonly string[];
 sectionRange: string;
 targetFilename: string;
 plan: EditPlan;
 compiled: Compilation;
 modelCalls: number;
 plannerCalls: number;
 /**
  * Ambient composite MIXED-batch only (design `sdd/proposal-deliberation-ambient-model`,
  * SLICE 1b): when one CREATE_SUCCESSOR call carries both in-place
  * (replace/insert/delete) and relocation (move/copy) decisions, `plan`/`compiled`
  * above freeze ONLY the in-place half against the CURRENT source. The
  * relocation half cannot be frozen the same way -- its byte offsets shift once
  * the in-place half publishes -- so its ORIGINAL, fuzzy, text-based locus
  * queries (never byte offsets) and already-validated decisions are deferred
  * here, to be RE-RESOLVED fresh against the in-place version's just-published
  * state at accept time (see `orchestrator.ts`'s `acceptAmbientCompositeSuccessor`).
  */
 pendingRelocation?: Readonly<{ queries: readonly string[]; oldEntryIds: readonly string[]; decisions: readonly EditAction[] }>;
}>;

type StoredPreview = FrozenSuccessorPreview & { token: string };

export type SuccessorAcceptanceRegistry = {
 create(sessionIdentity: string, preview: FrozenSuccessorPreview): string;
 consume(sessionIdentity: string, token: string): FrozenSuccessorPreview | undefined;
 clearSession(sessionIdentity: string): void;
};

function validSession(value: string): string {
 if (!value || value.includes('\0') || Buffer.byteLength(value) > 256) throw new Error('PI_SESSION_IDENTITY_INVALID');
 return value;
}

function immutablePreview(preview: FrozenSuccessorPreview): FrozenSuccessorPreview {
 return Object.freeze({ ...preview, plan: Object.freeze({ ...preview.plan, actions: [...preview.plan.actions], resolvedTargets: [...preview.plan.resolvedTargets] }), compiled: Object.freeze({ ...preview.compiled, patches: [...preview.compiled.patches], patchIds: [...preview.compiled.patchIds], modifiedRanges: [...preview.compiled.modifiedRanges], candidate: preview.compiled.candidate, sourceBytes: preview.compiled.sourceBytes ? Buffer.from(preview.compiled.sourceBytes) : undefined }) });
}

export function createSuccessorAcceptanceRegistry(tokenFactory: () => string = () => randomBytes(32).toString('base64url')): SuccessorAcceptanceRegistry {
 const sessions = new Map<string, Map<string, StoredPreview>>();
 return Object.freeze({
  create(sessionIdentity, preview) {
   const session = validSession(sessionIdentity);
   const token = tokenFactory();
   if (!TOKEN.test(token)) throw new Error('SUCCESSOR_ACCEPTANCE_TOKEN_INVALID');
   let values = sessions.get(session);
   if (!values) {
    if (sessions.size >= MAX_SESSIONS) sessions.delete(sessions.keys().next().value!);
    values = new Map(); sessions.set(session, values);
   }
   if (values.size >= MAX_PREVIEWS_PER_SESSION) values.delete(values.keys().next().value!);
   values.set(token, Object.freeze({ ...immutablePreview(preview), token }));
   return token;
  },
  consume(sessionIdentity, token) {
   const values = sessions.get(validSession(sessionIdentity));
   if (!values || !TOKEN.test(token)) return undefined;
   const preview = values.get(token);
   if (!preview) return undefined;
   values.delete(token);
   if (values.size === 0) sessions.delete(sessionIdentity);
   const { token: _token, ...frozen } = preview;
   return immutablePreview(frozen);
  },
  clearSession(sessionIdentity) { sessions.delete(validSession(sessionIdentity)); },
 });
}
