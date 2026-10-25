import { readFile } from 'node:fs/promises'; import { join } from 'node:path'; import { rebuildDerivedState } from './derived-state-builder.js'; import { loadDerivedState,saveDerivedState } from './derived-state-store.js'; import { PARSER_VERSION,sha256,type ContextFragment,type DocumentState } from './types.js'; import type { RevisionEvidence } from './revision-domain.js';
import { artifact,parseManagedRevision } from './artifact-naming.js';
// LAX PARSE is the sole gate here (measured, not assumed): it accepts ANY lineage character and a
// single ordinal digit, genuinely looser than the STRICT matcher used elsewhere. Collapsing it into
// STRICT would silently tighten `loadDocumentState` -- mutation M2b exists to catch exactly that.
const identity=parseManagedRevision;
export type DocumentStateLoadOptions = Readonly<{ readOnly?: boolean }>;

export async function loadDocumentState(root:string,filename:string,options:DocumentStateLoadOptions={}):Promise<DocumentState>{const m=identity(filename);if(!m)throw new Error('INVALID_MANAGED_REVISION');const bytes=await readFile(join(root,artifact.directory,filename));const rebuilt=await rebuildDerivedState(filename,m.revision,m.lineage,bytes);const cached=await loadDerivedState(root,filename,sha256(bytes),PARSER_VERSION,bytes);if(cached){return {...rebuilt,structuralIndex:cached.structuralIndex,referenceIndex:cached.referenceIndex,symbolIndex:cached.symbolIndex,conceptIndex:cached.conceptIndex,derivedStateStatus:cached.manifest.status,derivedStateManifest:cached.manifest};}if(options.readOnly)return rebuilt;await saveDerivedState(root,rebuilt);return rebuilt;}

/** Read-only scientific-context adapter: it never consults or writes derived-state caches. */
export function createReadOnlyDocumentFragmentLoader(root:string) {
 return {
  async load(input:{revision:RevisionEvidence;entryIds:string[];maxFragments:number;maxBytes:number}):Promise<{revision:RevisionEvidence;fragments:ContextFragment[]}> {
   const match=identity(input.revision.filename);
   if(!match||input.revision.revision!==match.revision) throw new Error('SCIENTIFIC_DOCUMENT_REVISION_INVALID');
   if(!Number.isSafeInteger(input.maxFragments)||input.maxFragments<0||!Number.isSafeInteger(input.maxBytes)||input.maxBytes<0) throw new Error('SCIENTIFIC_DOCUMENT_FRAGMENT_LIMIT_INVALID');
   const bytes=await readFile(join(root,artifact.directory,input.revision.filename));
   if(sha256(bytes)!==input.revision.documentSha256) throw new Error('SCIENTIFIC_DOCUMENT_REVISION_STALE');
   const state=await rebuildDerivedState(input.revision.filename,input.revision.revision,match.lineage,bytes);
   const fragments:ContextFragment[]=[];
   let consumed=0;
   for(const entryId of [...new Set(input.entryIds)].slice(0,input.maxFragments)) {
    const entry=state.structuralIndex.byId[entryId];
    if(!entry) continue;
    const text=bytes.subarray(entry.startByte,entry.endByte).toString('utf8');
    if(!text||consumed+Buffer.byteLength(text,'utf8')>input.maxBytes) break;
    consumed+=Buffer.byteLength(text,'utf8');
    fragments.push({entryId:entry.entryId,type:entry.type,text,textSha256:entry.textSha256,headingPath:[...entry.headingPath]});
   }
   return {revision:{...input.revision},fragments};
  },
 };
}
