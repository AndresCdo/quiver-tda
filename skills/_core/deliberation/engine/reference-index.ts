import type { ReferenceIndex, StructuralIndex } from './types.js';
import { DOMAIN, proseReference } from './domain-profile.js';
/**
 * How a proposal actually cites its own equations. `\eqref`/`\ref` need a
 * `\label`, which these documents do not use: they number with `\tag{N}` and
 * cite in prose as `(Ec. N)`. Left unrecognised, the reference index sees zero
 * references and its `missing` list is vacuously empty — so deleting a tagged
 * equation leaves every citation of it dangling with nothing to object.
 */
export const PROSE_REFERENCE=proseReference('g');

/**
 * Reference integrity (change 5): what a document DECLARES as a numbered/named thing, and
 * what CITES one, are `profile.references.{declares, cites}` lookups now — never a hardwired
 * `\label`/`\tag`/`\eqref`/`(Ec. N)` assumption. The mathematical vocabulary ships as
 * `the host-chosen profile's own reference module`, wired through `profile.ts`, exactly as the
 * preservation gate's `preservation-math.ts` (change 4).
 */

/** Every value this domain's document declares, per its own `declares` vocabulary. Defaults to the live profile; a second argument lets a different vocabulary be exercised directly, with no second real profile module needed. */
export function declaredValues(source:string, references=DOMAIN.references):readonly string[]{return references.declares(source).map(d=>d.value)}
/** Every value this domain's document cites, per its own `cites` vocabulary. */
export function citedValues(source:string, references=DOMAIN.references):readonly string[]{return references.cites(source).map(c=>c.value)}

/**
 * The reference-integrity algorithm itself, generic over any profile's `declares`/`cites`
 * vocabulary — extracted so a non-mathematical vocabulary shape can exercise it directly
 * (Acceptance Criteria: proven beyond the math profile's own tests), never coupled to the
 * live `DOMAIN` singleton a whole test run fixes to one domain.
 */
export function checkReferenceIntegrity(source:string, references=DOMAIN.references){
	const declared=declaredValues(source,references),cited=citedValues(source,references);
	const known=new Set(declared);
	return {
		declared,cited,
		unique:declared.length===new Set(declared).size,
		resolved:cited.every(value=>known.has(value)),
		applicable:declared.length>0||cited.length>0,
	};
}

export function buildReferenceIndex(source:string, index:StructuralIndex):ReferenceIndex {const labels:Record<string,string>={},tags:Record<string,string>={},duplicates:string[]=[],references:ReferenceIndex['references']=[]; for(const e of index.entries){const text=Buffer.from(source).subarray(e.startByte,e.endByte).toString(); for(const l of e.labels){if(labels[l])duplicates.push(`label:${l}`); else labels[l]=e.entryId} for(const t of e.tags){if(tags[t])duplicates.push(`tag:${t}`); else tags[t]=e.entryId} for(const c of DOMAIN.references.cites(text)) references.push({kind:c.kind,value:c.value,entryId:e.entryId});} return {labels,tags,references,duplicates,missing:references.filter(x=>!labels[x.value]&&!tags[x.value]).map(x=>x.value)};}
