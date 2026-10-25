// pi-free compatibility shim for `@earendil-works/pi-coding-agent`.
//
// Reproduces exactly the surface the deliberation engine consumes:
//   - types: ExtensionAPI, ExtensionContext, SessionShutdownEvent
//   - runtime: withFileMutationQueue (per-path async mutation serialization)
//
// The host (cli.mjs) supplies a concrete ExtensionContext; the engine logic is
// untouched. The ambient-model paradigm (design `sdd/proposal-deliberation-ambient-model`)
// removed the separate-model transport, so this context no longer carries a model
// identity or a model-auth registry (`ModelDescriptor`/`ApiKeyAndHeaders`/
// `getApiKeyAndHeaders` were removed as unreferenced once `production-runtime.ts`
// -- their only consumer -- was deleted).

import type { Static, TSchema } from 'typebox';

export interface SessionManager {
	getSessionId(): string;
}

export interface UI {
	confirm(title: string, message: string): Promise<boolean>;
}

/** Runtime context handed to the tool's execute(): the members the engine reads. */
export interface ExtensionContext {
	sessionManager: SessionManager;
	hasUI?: boolean;
	ui: UI;
}

export type SessionShutdownEvent = { reason: string };
export type SessionStartEvent = Record<string, unknown>;

type ExtensionEventHandler = (event: any, ctx: ExtensionContext) => unknown | Promise<unknown>;

/** The result shape every registered tool's `execute` resolves to. */
export type ToolExecuteResult = { content: Array<{ type: string; text: string }>; details: Record<string, unknown> };

/**
 * The tool shape `registerTool` accepts. `params` is the static type of the tool's own
 * `parameters` schema, so a handler declared inline needs no separate annotation.
 * `registerTool` keeps an `unknown` overload for tools built elsewhere whose hand-written
 * parameter types do not line up structurally with `Static<>` of their schema.
 */
export interface RegisteredTool<Schema extends TSchema = TSchema> {
	name: string;
	label: string;
	description: string;
	promptSnippet?: string;
	promptGuidelines?: readonly string[];
	parameters: Schema;
	execute(
		toolCallId: string,
		params: Static<Schema>,
		signal: AbortSignal | undefined,
		onUpdate: unknown,
		ctx: ExtensionContext,
	): Promise<ToolExecuteResult>;
}

/** The registration surface an extension factory uses. */
export interface ExtensionAPI {
	registerTool<Schema extends TSchema>(tool: RegisteredTool<Schema>): void;
	registerTool(tool: unknown): void;
	on(event: string, handler: ExtensionEventHandler): void;
}

// --- withFileMutationQueue -------------------------------------------------
// Serializes mutations per canonical target path so overlapping operations on
// the same file never interleave. Distinct paths run concurrently. This matches
// the pi runtime's file mutation queue semantics the engine relies on.

const queues = new Map<string, Promise<unknown>>();

export function withFileMutationQueue<T>(target: string, work: () => T | Promise<T>): Promise<T> {
	const previous = queues.get(target) ?? Promise.resolve();
	const run = previous.then(() => work());
	// Keep the chain alive even if `work` rejects, without swallowing the error
	// seen by the caller.
	const settled = run.then(
		() => undefined,
		() => undefined,
	);
	queues.set(target, settled);
	void settled.then(() => {
		if (queues.get(target) === settled) queues.delete(target);
	});
	return run;
}
