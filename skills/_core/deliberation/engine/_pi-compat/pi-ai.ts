// pi-free compatibility shim for `@earendil-works/pi-ai`.
//
// The engine uses a single helper from this package: `StringEnum`, which builds
// a TypeBox schema constraining a field to a fixed set of string literals. The
// implementation below is the canonical union-of-literals form: it validates
// under TypeBox `Value.Check` and serializes to valid JSON Schema for the model
// tool boundary — the two properties the engine and the transport depend on.

import { type Static, type TLiteral, type TSchema, type TSchemaOptions, type TUnion, Type } from 'typebox';

// TypeBox 1.x names the shared options bag `TSchemaOptions`, and `TUnion<Types>` constrains
// `Types extends TSchema[]` -- a mutable array. The homomorphic mapped type below preserves the
// tuple (so `Static<>` still yields the literal union rather than `never`), `-readonly` drops the
// readonly the `as const` argument carries in, and `Extract<..., TSchema[]>` is what lets the
// compiler see the result satisfying that constraint for an unresolved `T`.
type LiteralsOf<T extends readonly string[]> = Extract<{ -readonly [K in keyof T]: TLiteral<T[K] & string> }, TSchema[]>;

export function StringEnum<T extends readonly string[]>(
	values: T,
	options: TSchemaOptions = {},
): TUnion<LiteralsOf<T>> {
	const literals = values.map((value) => Type.Literal(value)) as [...LiteralsOf<T>];
	return Type.Union<LiteralsOf<T>>(literals, options);
}

export type StaticStringEnum<T extends readonly string[]> = Static<ReturnType<typeof StringEnum<T>>>;
