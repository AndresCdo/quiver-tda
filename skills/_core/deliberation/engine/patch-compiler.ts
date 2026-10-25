import { LIMITS,sha256,type Compilation,type CompiledPatch,type DocumentState,type EditPlan,type Position,type StructuralEntry,type StructuralPatchSelector } from './types.js'; import { expandDestructiveScope } from './destructive-scope.js'; import { composeSuccessorBlockCandidate } from './successor-composite-engine.js'; import type { SuccessorBlockPlan } from './block-plan.js'; import type { AmbientCompositePart } from './ambient-supplied-planner.js'; import { artifact } from './artifact-naming.js';
const text=(s:DocumentState,e:StructuralEntry)=>{const value=s.documentBytes.subarray(e.startByte,e.endByte).toString('utf8');if(sha256(value)!==e.textSha256)throw new Error('STALE_INDEX_ENTRY');return value};
const insertionPoint=(entry:StructuralEntry,position:Position)=>{if(position==='before')return {point:entry.startByte,adapterPosition:'before' as const};if(position==='after'||position==='inside_end')return {point:entry.endByte,adapterPosition:'after' as const};throw new Error('UNSUPPORTED_INSIDE_START')};
const apply=(base:Buffer,edits:{start:number;end:number;value:Buffer}[])=>edits.sort((a,b)=>b.start-a.start).reduce((candidate,e)=>Buffer.concat([candidate.subarray(0,e.start),e.value,candidate.subarray(e.end)]),base);
// Finding M7: was a hardcoded `Buffer.from('<!-- proposal-workspace:artifact:v1 -->\n')` --
// a domain declaring its own `artifact.marker` had its successor section-replacement
// boundary logic (`protectedMarker` below) silently compare against the WRONG bytes.
// Read from the profile, like every other core site except `revision-lifecycle-store.ts`
// (kept hardcoded on purpose, for a Python cross-language regex guard).
const ARTIFACT_MARKER=artifact.marker;
const trailingNewlines=(value:Buffer)=>{let index=value.length;while(index>0&&value[index-1]===0x0a){index--;if(index>0&&value[index-1]===0x0d)index--;}return index;};
const leadingNewlines=(value:Buffer)=>{let index=0;while(index<value.length){if(value[index]===0x0d&&value[index+1]===0x0a)index+=2;else if(value[index]===0x0a)index++;else break;}return index;};
function compileSuccessorSectionReplacement(state:DocumentState,entry:StructuralEntry,replacementText:string){
 const targetContract=entry.type==='composite'?entry.sectionReplacement:undefined;
 const source=Buffer.from(state.documentBytes),replacement=Buffer.from(replacementText);
 if(!targetContract)throw new Error('SUCCESSOR_SECTION_REPLACEMENT_CONTRACT_REQUIRED');
 const {startByte,endByte,newline,startAtLineStart,endAfterCompleteLine}=targetContract;
 const detected=source.includes(Buffer.from('\r\n'))?'\r\n':'\n';
 if(startByte!==entry.startByte||endByte!==entry.endByte||newline!==detected||!startAtLineStart||!endAfterCompleteLine||(startByte!==0&&source[startByte-1]!==0x0a)||(endByte!==source.length&&source[endByte-1]!==0x0a))throw new Error('SUCCESSOR_SECTION_REPLACEMENT_CONTRACT_INVALID');
 const prefix=source.subarray(0,startByte),suffix=source.subarray(endByte);
 const protectedMarker=prefix.equals(ARTIFACT_MARKER);
 const prefixCore=protectedMarker?prefix:prefix.subarray(0,trailingNewlines(prefix));
 const replacementCore=replacement.subarray(leadingNewlines(replacement),trailingNewlines(replacement));
 const suffixCore=suffix.subarray(leadingNewlines(suffix));
 const leftBoundary=prefixCore.length>0&&!protectedMarker&&replacementCore.length>0;
 const rightBoundary=suffixCore.length>0&&replacementCore.length>0;
 const joiner=Buffer.from(`${newline}${newline}`);
 const value=Buffer.concat([...(leftBoundary?[joiner]:[]),replacementCore,...(rightBoundary?[joiner]:[]),...(replacementCore.length===0&&prefixCore.length>0&&suffixCore.length>0&&!protectedMarker?[joiner]:[])]);
 const start=prefixCore.length,end=source.length-suffixCore.length;
 const candidate=Buffer.concat([prefixCore,value,suffixCore]);
 return {start,end,value,candidate,oldText:source.subarray(start,end).toString('utf8'),newText:value.toString('utf8'),selector:start===startByte&&end===endByte?{entryId:entry.entryId,startByte,endByte,textSha256:entry.textSha256,documentSha256:state.documentSha256}:undefined};
}
export function compilePatches(state:DocumentState,plan:EditPlan):Compilation {if(plan.documentSha256!==state.documentSha256)throw new Error('STALE_DOCUMENT_SHA');const successorCompositeTarget=plan.successorCompositeTarget===true;const max=successorCompositeTarget?1:(plan.intent==='CONCEPTUAL_REVISION'?3:(plan.intent==='MODIFY'&&plan.semanticChange?1:LIMITS.maxPatchCountLocal));if(plan.actions.length>max)throw new Error(successorCompositeTarget?'SUCCESSOR_EXACTLY_ONE_REPLACE_REQUIRED':'PATCH_BUDGET_EXCEEDED');if(successorCompositeTarget&&(plan.actions.length!==1||plan.resolvedTargets.length!==1||plan.actions.some(action=>action.kind!=='replace'||action.targetEntryId!==plan.resolvedTargets[0]||state.structuralIndex.byId[action.targetEntryId]?.type!=='composite')))throw new Error('SUCCESSOR_COMPOSITE_TARGET_REQUIRED');
 const moveCopy=plan.actions.length===1&&(plan.actions[0].kind==='move'||plan.actions[0].kind==='copy');if(moveCopy){const a:any=plan.actions[0],source=state.structuralIndex.byId[a.sourceEntryIds[0]],destination=state.structuralIndex.byId[a.destinationAnchorId];if(!source||!destination)throw new Error('UNKNOWN_TARGET');if(source.entryId===destination.entryId)throw new Error('SOURCE_EQUALS_DESTINATION');const sourceText=text(state,source),destinationText=text(state,destination),point=insertionPoint(destination,a.position);if(point.point>source.startByte&&point.point<source.endByte)throw new Error('INVALID_DESTINATION_INSIDE_SOURCE');const content=a.moveMode==='ADAPTIVE'?a.transformedContent:sourceText;if(!content)throw new Error('EMPTY_MOVE_COPY_CONTENT');if(a.moveMode==='LITERAL'&&content!==sourceText)throw new Error('LITERAL_BYTES_CHANGED');const separator='\n\n',replacement=`${separator}${point.adapterPosition==='before'?`${content}${separator}${destinationText}`:`${destinationText}${separator}${content}`}${separator}`;const edits=a.kind==='move'?[{start:source.startByte,end:source.endByte,value:Buffer.alloc(0)},{start:destination.startByte,end:destination.endByte,value:Buffer.from(replacement)}]:[{start:destination.startByte,end:destination.endByte,value:Buffer.from(replacement)}];const candidate=apply(Buffer.from(state.documentBytes),edits);if(candidate.equals(state.documentBytes))throw new Error('NO_OP_PLAN');const patches:any[]=[];if(a.kind==='move')patches.push({id:'',kind:'replace',oldText:sourceText,newText:''});patches.push({id:'',kind:'replace',oldText:destinationText,newText:replacement});const compiledPatches=patches.map((patch,index)=>({...patch,id:`patch-${index+1}`}));return {patches:compiledPatches,candidate:candidate.toString(),candidateSha256:sha256(candidate),patchIds:compiledPatches.map(x=>x.id),unchangedByteCoverage:true,modifiedRanges:edits.map(e=>({startByte:e.start,endByte:e.end})),sourceBytes:Buffer.from(sourceText),destinationEntryId:destination.entryId,position:a.position};}
 const edits:{start:number;end:number;value:Buffer;patch:any}[]=[];for(const action of plan.actions){if(action.kind==='replace'){const e=state.structuralIndex.byId[action.targetEntryId];if(!e)throw new Error('UNKNOWN_TARGET');if(successorCompositeTarget){const replacement=compileSuccessorSectionReplacement(state,e,action.replacementText);edits.push({start:replacement.start,end:replacement.end,value:replacement.value,patch:{id:`replace-${e.entryId}`,kind:'replace',oldText:replacement.oldText,newText:replacement.newText,...(replacement.selector?{selector:replacement.selector}:{})}})}else{const old=text(state,e);if(old===action.replacementText)throw new Error('NO_OP_PLAN');edits.push({start:e.startByte,end:e.endByte,value:Buffer.from(action.replacementText),patch:{id:`replace-${e.entryId}`,kind:'replace',oldText:old,newText:action.replacementText,selector:{entryId:e.entryId,startByte:e.startByte,endByte:e.endByte,textSha256:e.textSha256,documentSha256:state.documentSha256}}})}}else if(action.kind==='insert'){const e=state.structuralIndex.byId[action.anchorEntryId];if(!e)throw new Error('UNKNOWN_TARGET');const point=insertionPoint(e,action.position);edits.push({start:point.point,end:point.point,value:Buffer.from(action.content),patch:{id:`insert-${e.entryId}`,kind:'insert',anchor:text(state,e),position:point.adapterPosition,content:action.content}})}else if(action.kind==='delete'){if(!plan.destructiveIntent)throw new Error('UNAUTHORIZED_DELETION');const e=state.structuralIndex.byId[action.targetEntryId];if(!e)throw new Error('UNKNOWN_TARGET');const scope=expandDestructiveScope(state,e);const old=state.documentBytes.subarray(scope.startByte,scope.endByte).toString();if(!old)throw new Error('NO_OP_PLAN');edits.push({start:scope.startByte,end:scope.endByte,value:Buffer.alloc(0),patch:{id:`delete-${e.entryId}`,kind:'replace',oldText:old,newText:'',selector:{entryId:e.entryId,startByte:scope.startByte,endByte:scope.endByte,textSha256:sha256(state.documentBytes.subarray(scope.startByte,scope.endByte)),documentSha256:state.documentSha256}}})}else if(action.kind==='cleanup'){for(const id of action.boundedRangeIds){const e=state.structuralIndex.byId[id];if(!e||e.type==='display_equation')throw new Error('CLEANUP_EQUATION_FORBIDDEN');const old=text(state,e);const value=action.action==='delete'?'':old.replace(/^\s*\n+|\n+\s*$/g,'');if(old===value)continue;edits.push({start:e.startByte,end:e.endByte,value:Buffer.from(value),patch:{id:`cleanup-${e.entryId}`,kind:'replace',oldText:old,newText:value}})}}else if(action.kind==='rewrite_transition'){const e=state.structuralIndex.byId[action.boundedRangeId];if(!e||e.type==='display_equation')throw new Error('CLEANUP_EQUATION_FORBIDDEN');const old=text(state,e);edits.push({start:e.startByte,end:e.endByte,value:Buffer.from(action.replacementText),patch:{id:`cleanup-${e.entryId}`,kind:'replace',oldText:old,newText:action.replacementText}})}else throw new Error('UNSUPPORTED_ACTION_PROFILE');}
 if(!edits.length)throw new Error('NO_OP_PLAN');for(const [i,e] of edits.entries())for(const other of edits.slice(i+1))if(e.start<other.end&&other.start<e.end)throw new Error('OVERLAPPING_PATCHES');const candidate=apply(Buffer.from(state.documentBytes),edits);if(candidate.equals(state.documentBytes))throw new Error('NO_OP_PLAN');const patches=edits.map((x,index)=>({...x.patch,id:`patch-${index+1}`}));if(successorCompositeTarget){const edit=edits[0],suffix=state.documentBytes.subarray(edit.end);if(!candidate.subarray(0,edit.start).equals(state.documentBytes.subarray(0,edit.start))||!candidate.subarray(candidate.length-suffix.length).equals(suffix))throw new Error('SUCCESSOR_BYTE_PRESERVATION_FAILED');}return {patches,candidate:candidate.toString(),candidateSha256:sha256(candidate),patchIds:patches.map(p=>p.id),unchangedByteCoverage:true,modifiedRanges:edits.map(e=>({startByte:e.start,endByte:e.end}))};}

/**
 * Mirrors `successor-composite-engine.ts`'s private `spliceDisjoint` exactly;
 * duplicated locally (rather than exported from that module) so this module
 * can precompute each block's expected per-transition candidate hash before
 * calling `composeSuccessorBlockCandidate`, without widening the composite
 * engine's own minimal public contract.
 */
function spliceDisjointForCandidateHash(source:Buffer,edits:readonly{startByte:number;endByte:number;replacement:Buffer}[]):Buffer{
 const ordered=[...edits].sort((left,right)=>left.startByte-right.startByte);
 const parts:Buffer[]=[];let cursor=0;
 for(const edit of ordered){parts.push(source.subarray(cursor,edit.startByte));parts.push(edit.replacement);cursor=edit.endByte;}
 parts.push(source.subarray(cursor));
 return Buffer.concat(parts);
}

/**
 * Byte-preserving successor compile path for the interactive CREATE_SUCCESSOR
 * pipeline (orchestrator.ts). Unlike `compilePatches`'s successor branch
 * (`compileSuccessorSectionReplacement`, kept unchanged above for its own
 * direct callers/tests), this NEVER reformats or normalizes bytes adjacent to
 * the edited span: each approved replacement text is spliced verbatim at its
 * resolved locus's exact byte offsets via the disjoint-splice composite
 * engine (`successor-composite-engine.ts`), which independently re-verifies
 * that every byte outside the union of spans is untouched
 * (`COMPOSITE_UNTOUCHED_INVARIANT`).
 *
 * Supports ONE OR MORE resolved, disjoint targets (design amendment: multi-
 * section successor): `plan.resolvedTargets`/`plan.actions` may name several
 * independent composite loci; every one of them is spliced into the SAME
 * successor candidate in one pass. Duplicate or byte-overlapping targets are
 * rejected explicitly rather than silently applied.
 */
export async function compileSuccessorCompositeReplacement(state:DocumentState,plan:EditPlan):Promise<Compilation> {
 if(plan.documentSha256!==state.documentSha256)throw new Error('STALE_DOCUMENT_SHA');
 if(plan.successorCompositeTarget!==true||!plan.actions.length||plan.actions.length!==plan.resolvedTargets.length)throw new Error('SUCCESSOR_COMPOSITE_TARGET_REQUIRED');
 if(new Set(plan.resolvedTargets).size!==plan.resolvedTargets.length)throw new Error('SUCCESSOR_DUPLICATE_TARGET');
 const resolved=plan.resolvedTargets.map(targetEntryId=>{
  const action=plan.actions.find(candidate=>candidate.kind==='replace'&&candidate.targetEntryId===targetEntryId) as Extract<EditPlan['actions'][number],{kind:'replace'}>|undefined;
  if(!action)throw new Error('SUCCESSOR_COMPOSITE_TARGET_REQUIRED');
  const entry=state.structuralIndex.byId[targetEntryId];
  if(!entry||entry.type!=='composite')throw new Error('SUCCESSOR_COMPOSITE_TARGET_REQUIRED');
  const oldText=text(state,entry);
  if(oldText===action.replacementText)throw new Error('NO_OP_PLAN');
  const selector:StructuralPatchSelector={entryId:entry.entryId,startByte:entry.startByte,endByte:entry.endByte,textSha256:entry.textSha256,documentSha256:state.documentSha256};
  return {oldText,replacementText:action.replacementText,selector};
 });
 const ordered=[...resolved].sort((left,right)=>left.selector.startByte-right.selector.startByte);
 for(let index=1;index<ordered.length;index++)if(ordered[index].selector.startByte<ordered[index-1].selector.endByte)throw new Error('SUCCESSOR_TARGET_OVERLAP');
 const blockIds=ordered.map((_,index)=>`successor-block-${index+1}`);
 const blocks=ordered.map((item,index)=>{
  const subsetEdits=ordered.slice(0,index+1).map(candidate=>({startByte:candidate.selector.startByte,endByte:candidate.selector.endByte,replacement:Buffer.from(candidate.replacementText,'utf8')}));
  return {id:blockIds[index],dependsOn:[],target:{status:'resolved' as const,selector:item.selector},candidateSha256:sha256(spliceDisjointForCandidateHash(state.documentBytes,subsetEdits))};
 });
 const blockPlan:SuccessorBlockPlan={source:{filename:state.filename,revision:state.revision,documentSha256:state.documentSha256},orderedBlockIds:blockIds,blocks,mergeGroups:[]};
 const result=await composeSuccessorBlockCandidate(blockPlan,state,({entryId})=>ordered.find(candidate=>candidate.selector.entryId===entryId)!.replacementText);
 if(result.status!=='composed'){
  const code=result.diagnostics[0]?.code;
  if(code==='COMPOSITE_NO_OP')throw new Error('NO_OP_PLAN');
  if(code==='COMPOSITE_UNTOUCHED_INVARIANT')throw new Error('SUCCESSOR_BYTE_PRESERVATION_FAILED');
  throw new Error(`SUCCESSOR_COMPOSITE_PLAN_INVALID:${code??'UNKNOWN'}`);
 }
 const patches=ordered.map((item,index)=>({id:`patch-${index+1}`,kind:'replace' as const,oldText:item.oldText,newText:item.replacementText,selector:item.selector}));
 return {patches,candidate:result.candidateBytes.toString('utf8'),candidateSha256:result.manifest.candidateSha256,patchIds:patches.map(patch=>patch.id),unchangedByteCoverage:true,modifiedRanges:ordered.map(item=>({startByte:item.selector.startByte,endByte:item.selector.endByte}))};
}

/**
 * Byte-preserving successor compile path for ANY-kind resolved decisions
 * (design `sdd/proposal-deliberation-ambient-model`, SLICE 1b): unlike
 * `compileSuccessorCompositeReplacement` above (kept unchanged, replace-only,
 * still the exact path `edit-planner.ts`'s hard MODIFY invariant requires),
 * this accepts pre-reduced `AmbientCompositePart[]` (`ambient-supplied-planner.ts`'s
 * `resolveAmbientCompositeDecisions`) carrying an explicit `op` -- `replace`,
 * `insert` (zero-width anchor splice), or `delete` (empty replacement over a
 * non-empty span) -- one or two parts per decision (`move` contributes both an
 * insert-at-destination and a delete-at-source part; every other kind
 * contributes exactly one). Every part is spliced through the SAME disjoint,
 * source-frozen `composeSuccessorBlockCandidate` engine, so
 * `COMPOSITE_UNTOUCHED_INVARIANT`, the `(startByte,endByte)` tie-break, and
 * overlap/no-op rejection apply identically regardless of operation kind.
 */
export async function compileSuccessorCompositeChangeset(state:DocumentState,parts:readonly AmbientCompositePart[]):Promise<Compilation> {
 if(!parts.length)throw new Error('NO_MUTATION_PLAN');
 const ordered=[...parts].sort((left,right)=>left.startByte-right.startByte||left.endByte-right.endByte);
 for(let index=1;index<ordered.length;index++)if(ordered[index].startByte<ordered[index-1].endByte)throw new Error('SUCCESSOR_TARGET_OVERLAP');
 const blockIds=ordered.map((_,index)=>`successor-block-${index+1}`);
 const blocks=ordered.map((item,index)=>{
  const subsetEdits=ordered.slice(0,index+1).map(candidate=>({startByte:candidate.startByte,endByte:candidate.endByte,replacement:Buffer.from(candidate.replacementText,'utf8')}));
  return {id:blockIds[index],dependsOn:[],target:{status:'resolved' as const,selector:{entryId:item.entryId,startByte:item.startByte,endByte:item.endByte,textSha256:item.textSha256,documentSha256:state.documentSha256}},candidateSha256:sha256(spliceDisjointForCandidateHash(state.documentBytes,subsetEdits)),op:item.op};
 });
 const blockPlan:SuccessorBlockPlan={source:{filename:state.filename,revision:state.revision,documentSha256:state.documentSha256},orderedBlockIds:blockIds,blocks,mergeGroups:[]};
 const byBlockId=new Map(blockIds.map((id,index)=>[id,ordered[index]]));
 const result=await composeSuccessorBlockCandidate(blockPlan,state,({block})=>byBlockId.get(block.id)!.replacementText);
 if(result.status!=='composed'){
  const code=result.diagnostics[0]?.code;
  if(code==='COMPOSITE_NO_OP')throw new Error('NO_OP_PLAN');
  if(code==='COMPOSITE_UNTOUCHED_INVARIANT')throw new Error('SUCCESSOR_BYTE_PRESERVATION_FAILED');
  throw new Error(`SUCCESSOR_COMPOSITE_PLAN_INVALID:${code??'UNKNOWN'}`);
 }
 const patches:CompiledPatch[]=ordered.map((item,index)=>{
  const id=`patch-${index+1}`;
  if(item.op==='insert'){
   const entry=state.structuralIndex.byId[item.entryId];
   const anchor=entry?state.documentBytes.subarray(entry.startByte,entry.endByte).toString('utf8'):'';
   return {id,kind:'insert' as const,anchor,position:item.position??'after',content:item.replacementText};
  }
  const oldText=state.documentBytes.subarray(item.startByte,item.endByte).toString('utf8');
  return {id,kind:'replace' as const,oldText,newText:item.replacementText,selector:{entryId:item.entryId,startByte:item.startByte,endByte:item.endByte,textSha256:item.textSha256,documentSha256:state.documentSha256}};
 });
 return {patches,candidate:result.candidateBytes.toString('utf8'),candidateSha256:result.manifest.candidateSha256,patchIds:patches.map(patch=>patch.id),unchangedByteCoverage:true,modifiedRanges:ordered.map(item=>({startByte:item.startByte,endByte:item.endByte}))};
}
