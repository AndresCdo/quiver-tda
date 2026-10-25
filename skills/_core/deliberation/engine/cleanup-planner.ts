import { LIMITS,type CleanupLevel,type DocumentState,type EditAction } from './types.js';
export type CleanupPlan={documentSha256:string;cleanupLevel:CleanupLevel;boundedEntryIds:string[];actions:Extract<EditAction,{kind:'cleanup'|'rewrite_transition'}>[];instructionEvidence:string[];reasons:string[];unresolvedQuestions:string[]};
export function validateCleanupPlan(state:DocumentState,plan:CleanupPlan,allowed:string[],semanticAuthorized:boolean){
 if(plan.cleanupLevel==='NONE'&&plan.actions.length)throw new Error('CLEANUP_NONE_HAS_ACTIONS');if(plan.cleanupLevel==='SEMANTIC'&&!semanticAuthorized)throw new Error('SEMANTIC_CLEANUP_UNAUTHORIZED');if(plan.actions.length>LIMITS.maxCleanupRanges)throw new Error('CLEANUP_RANGE_BUDGET_EXCEEDED');
 for(const id of plan.boundedEntryIds)if(!allowed.includes(id))throw new Error('CLEANUP_OUTSIDE_BOUNDS');
 for(const action of plan.actions){const ids=action.kind==='cleanup'?action.boundedRangeIds:[action.boundedRangeId];if(ids.some(id=>!plan.boundedEntryIds.includes(id)||!allowed.includes(id)))throw new Error('PLANNER_INVENTED_ENTRY_ID');for(const id of ids)if(state.structuralIndex.byId[id]?.type==='display_equation')throw new Error('CLEANUP_EQUATION_FORBIDDEN');}
 return true;
}
