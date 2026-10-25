import type { DocumentState, StructuralEntry } from './types.js';
export type DestructiveInspection={entryIds:string[]; startByte:number; endByte:number; labels:string[]; tags:string[]; references:string[]; definedSymbols:string[]; laterSymbolUses:string[]; requiresStructuralCleanup:boolean};
export function expandDestructiveScope(state:DocumentState, entry:StructuralEntry):DestructiveInspection {
 const entries=state.structuralIndex.entries; let start=entry.startByte,end=entry.endByte; const isHeading=['section','subsection','heading'].includes(entry.type);
 if(isHeading){const level=entry.type==='section'?1:entry.type==='subsection'?2:3;const source=state.documentBytes.toString('utf8');const headings=[...source.matchAll(/^(#{1,6})\s+.*$/gm)].map(x=>({level:x[1].length,start:Buffer.byteLength(source.slice(0,x.index)),index:x.index!}));const current=headings.findIndex(x=>x.start===entry.startByte);const next=headings.slice(current+1).find(x=>x.level<=level);end=next?.start??state.documentBytes.length;}
 const body=state.documentBytes.subarray(start,end).toString('utf8');const rest=state.documentBytes.subarray(end).toString('utf8');
 const labels=[...body.matchAll(/\\label\{([^}]+)\}/g)].map(x=>x[1]);const tags=[...body.matchAll(/\\tag\{([^}]+)\}/g)].map(x=>x[1]);
 const references=[...rest.matchAll(/\\(?:eqref|ref)\{([^}]+)\}/g)].map(x=>x[1]).filter(x=>labels.includes(x)||tags.includes(x));
 const definedSymbols=[...body.matchAll(/(?:^|[^\\])\b([A-Za-z][A-Za-z0-9_]*)\s*(?:=|\\in|:)/gm)].map(x=>x[1]);
 const laterSymbolUses=definedSymbols.filter(s=>new RegExp(`\\b${s}\\b`).test(rest));
 return {entryIds:entries.filter(x=>x.startByte>=start&&x.endByte<=end).map(x=>x.entryId),startByte:start,endByte:end,labels,tags,references,definedSymbols,laterSymbolUses,requiresStructuralCleanup:isHeading&&body.trim().length>0};
}
