import { sha256, type EntryType, type StructuralEntry, type StructuralIndex } from './types.js';
import { DOMAIN } from './domain-profile.js';
const terms=(text:string)=>[...new Set((text.toLowerCase().match(/[\p{L}\p{N}_-]{2,}/gu)??[]))];
// Change 5: the PATTERN each declaration kind matches is now `profile.references.declares`,
// never a hardwired `\label{}`/`\tag{}` regex. Structural indexing still tracks the two kinds
// by NAME ("label"/"tag") for locus lookup (`target-resolver.ts` matches an explicit
// `\label`/`\tag` selection, untouched by this change) -- a domain whose vocabulary declares
// no "label"/"tag" split simply produces two empty arrays here, harmless: nothing in this
// engine requires them non-empty, and `target-resolver.ts` already ORs the two together. The
// reference-INTEGRITY check itself (`reference-index.ts`'s `checkReferenceIntegrity`) reads
// `declares`/`cites` directly and is fully vocabulary-agnostic, never going through this split.
const declaredBy=(text:string, kind:string)=>DOMAIN.references.declares(text).filter(d=>d.kind===kind).map(d=>d.value);
const labels=(text:string)=>declaredBy(text,'label');
const tags=(text:string)=>declaredBy(text,'tag');
// A GFM table, fully pipe-delimited (every row opens and closes with `|`): a header row,
// its `---`/`:---:` alignment separator, then zero or more body rows. Recognizing only the
// fully-piped form keeps this unambiguous against ordinary prose that happens to contain a
// stray `|`, matching the convention already used by every fixture in this engine.
const GFM_TABLE=/^\|[^\n]*\|[ \t]*\r?\n\|(?:[ \t]*:?-+:?[ \t]*\|)+[ \t]*\r?\n(?:\|[^\n]*\|[ \t]*(?:\r?\n|$))*/gm;
// A declared figure placeholder: a Markdown image reference standing alone on its own line.
const FIGURE_PLACEHOLDER=/^!\[[^\]\n]*\]\([^)\n]*\)[ \t]*$/gm;
export function buildStructuralIndex(source:string):StructuralIndex {
 const chunks:{type:EntryType;start:number;end:number;path:string[];ordinal:number}[]=[]; const headings=[...source.matchAll(/^#{1,6}\s+(.+)$/gm)];
 chunks.push({type:'document',start:0,end:Buffer.byteLength(source),path:[],ordinal:0});
 headings.forEach((m,i)=>{const level=m[0].indexOf(' '); const start=m.index!; const end=i+1<headings.length?headings[i+1].index!:source.length; const path=headings.slice(0,i+1).filter(h=>h[0].indexOf(' ')<=level).map(h=>h[1].trim()); chunks.push({type:level===1?'section':level===2?'subsection':'heading',start,end,path,ordinal:i});});
 const displays=[...source.matchAll(/^\$\$\r?\n[\s\S]*?^\$\$\s*$/gm)]; displays.forEach((m,i)=>chunks.push({type:'display_equation',start:m.index!,end:m.index!+m[0].length,path:headingPath(headings,m.index!),ordinal:i}));
 // Tables and figure placeholders are detected as their own spans BEFORE paragraph
 // boundaries are computed, so a paragraph never re-claims bytes already owned by one of
 // these (change 6: a retyping, and additive only when neither exists in a document).
 const tables=[...source.matchAll(GFM_TABLE)].map(m=>({start:m.index!,end:m.index!+m[0].replace(/\r?\n$/,'').length}));
 tables.forEach((t,i)=>chunks.push({type:'table',start:t.start,end:t.end,path:headingPath(headings,t.start),ordinal:i}));
 const figures=[...source.matchAll(FIGURE_PLACEHOLDER)].map(m=>({start:m.index!,end:m.index!+m[0].length}));
 figures.forEach((f,i)=>chunks.push({type:'figure_placeholder',start:f.start,end:f.end,path:headingPath(headings,f.start),ordinal:i}));
 const special=[...tables,...figures];
 const overlapsSpecial=(start:number,end:number)=>special.some(r=>start<r.end&&end>r.start);
 const boundaries=[...source.matchAll(/(?:^|\n\n)(?!#|\$\$)([^\n][\s\S]*?)(?=\n\n|$)/g)]; boundaries.forEach((m,i)=>{const text=m[1]; const start=(m.index??0)+m[0].indexOf(text); if(!text.includes('$$')&&!overlapsSpecial(start,start+text.length)) chunks.push({type:'paragraph',start,end:start+text.length,path:headingPath(headings,start),ordinal:i});});
 const sorted=chunks.sort((a,b)=>a.start-b.start||a.end-b.end); const entries=sorted.map((c,i):StructuralEntry=>{const text=source.slice(c.start,c.end); const parent=sorted.filter(x=>x.start<=c.start&&x.end>=c.end&&x!==c).sort((a,b)=>(a.end-a.start)-(b.end-b.start))[0]; const id=`${c.type}:${sha256(`${parent?.type??'root'}:${c.ordinal}:${sha256(text)}`).slice(0,24)}`; return {entryId:id,type:c.type,startByte:Buffer.byteLength(source.slice(0,c.start)),endByte:Buffer.byteLength(source.slice(0,c.end)),textSha256:sha256(text),parentId:parent?`${parent.type}:${parent.ordinal}`:undefined,childIds:[],ordinal:c.ordinal,headingPath:c.path,labels:labels(text),tags:tags(text),lexicalTerms:terms(text),deterministicAliases:[...labels(text),...tags(text),...c.path.map(x=>x.toLowerCase())],neighboringEntryIds:[]};});
 entries.forEach((e,i)=>e.neighboringEntryIds=[entries[i-1]?.entryId,entries[i+1]?.entryId].filter(Boolean) as string[]); return {entries,byId:Object.fromEntries(entries.map(e=>[e.entryId,e]))};
}
function headingPath(headings:RegExpMatchArray[], at:number){return headings.filter(h=>(h.index??0)<=at).slice(-3).map(h=>h[1].trim());}
export function entryText(state:{documentBytes:Buffer}, entry:StructuralEntry){const text=state.documentBytes.toString('utf8'); const bytes=state.documentBytes; const value=bytes.subarray(entry.startByte,entry.endByte).toString('utf8'); if(sha256(value)!==entry.textSha256) throw new Error('STALE_INDEX_ENTRY'); return value;}
