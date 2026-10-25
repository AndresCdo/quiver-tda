import { LIMITS,sha256,type ContextFragment,type DocumentState,type FidelityConstraints,type LocalContext,type MoveCopyContext } from './types.js';
const text=(state:DocumentState,id:string)=>{const e=state.structuralIndex.byId[id];return e?state.documentBytes.subarray(e.startByte,e.endByte).toString('utf8'):''};
export function buildContext(state:DocumentState,ids:string[],instruction='',fidelity?:FidelityConstraints,authorizedEntryIds?:string[]):LocalContext {
 const targetEntryId=ids[0]; const target=state.structuralIndex.byId[targetEntryId]; if(!target)throw new Error('UNKNOWN_CONTEXT_TARGET');
 const selected:string[]=authorizedEntryIds?.length?[...authorizedEntryIds]:[targetEntryId,...target.neighboringEntryIds]; const targetSymbols=new Set((text(state,targetEntryId).match(/\\[A-Za-z]+|\b[A-Za-z]\b/g)??[]).map(x=>x.replace(/^\\/,'').toLowerCase()));
 for(const symbol of Object.values(state.symbolIndex.symbols))if(targetSymbols.has(symbol.normalized)&&!selected.includes(symbol.firstEntryId))selected.push(symbol.firstEntryId);
 const fragments:ContextFragment[]=[];let bytes=0;for(const id of [...new Set(selected)]){if(fragments.length>=LIMITS.maxContextFragments)break;const e=state.structuralIndex.byId[id];const value=text(state,id);const size=Buffer.byteLength(value);if(!e||!value||bytes+size>LIMITS.maxContextBytesLocal)continue;bytes+=size;fragments.push({entryId:id,type:e.type,text:value,textSha256:sha256(value),headingPath:e.headingPath});}
 const nearbySymbols=Object.fromEntries(Object.entries(state.symbolIndex.symbols).filter(([,s])=>fragments.some(f=>f.entryId===s.firstEntryId||s.uses.includes(f.entryId))).map(([name,s])=>[name,s.definition??'']));
 const directReferences=state.referenceIndex.references.filter(r=>fragments.some(f=>f.entryId===r.entryId)).map(r=>`${r.kind}:${r.value}`);
 return {documentSha256:state.documentSha256,targetEntryId,instruction,fragments,nearbySymbols,directReferences,fidelity,...(authorizedEntryIds?.length?{authorizedEntryIds:[...authorizedEntryIds]}:{})};
}
/** Builds one exact composite successor boundary; it never adds neighbors, symbols, or partial fragments. */
export function buildSuccessorCompositeContext(state:DocumentState,entryId:string,instruction=''):LocalContext {
 const entry=state.structuralIndex.byId[entryId];
 if(!entry||entry.type!=='composite')throw new Error('SUCCESSOR_COMPOSITE_TARGET_REQUIRED');
 const value=text(state,entryId),bytes=Buffer.byteLength(value);
 if(!value||bytes>LIMITS.maxContextBytesSection)throw new Error('SUCCESSOR_CONTEXT_TOO_LARGE');
 const fragment:ContextFragment={entryId,type:'composite',text:value,textSha256:sha256(value),headingPath:entry.headingPath};
 return {documentSha256:state.documentSha256,targetEntryId:entryId,instruction,fragments:[fragment],nearbySymbols:{},directReferences:[],maxBytes:LIMITS.maxContextBytesSection,authorizedEntryIds:[entryId],successorCompositeTarget:true};
}
export function buildMoveCopyContext(state:DocumentState,sourceEntryId:string,destinationEntryId:string,instruction=''):MoveCopyContext {
 const sourceContext=buildContext(state,[sourceEntryId],instruction);const destinationContext=buildContext(state,[destinationEntryId],instruction);const fragments:ContextFragment[]=[];let bytes=0;
 for(const fragment of [...sourceContext.fragments,...destinationContext.fragments]){if(fragments.some(x=>x.entryId===fragment.entryId)||fragments.length>=8)continue;const size=Buffer.byteLength(fragment.text);if(bytes+size>32000)continue;bytes+=size;fragments.push(fragment);}
 return {documentSha256:state.documentSha256,instruction,sourceContext:{...sourceContext,fragments:fragments.filter(f=>sourceContext.fragments.some(x=>x.entryId===f.entryId))},destinationContext:{...destinationContext,fragments:fragments.filter(f=>destinationContext.fragments.some(x=>x.entryId===f.entryId))},fragments};
}
