import type { ConceptIndex, StructuralIndex } from './types.js';
export function buildConceptIndex(source:string,index:StructuralIndex):ConceptIndex {const terms:Record<string,string[]>={};for(const e of index.entries)for(const t of e.lexicalTerms){(terms[t]??=[]).push(e.entryId)} return {terms,aliases:Object.fromEntries(Object.entries(terms).map(([k,v])=>[k.replace(/[-_]/g,' '),v]))};}
