import { LIMITS } from './types.js';

export type RouteMetricStage = 'LIFECYCLE' | 'DIRECT_DOCUMENT' | 'CHAT_DELIBERATION' | 'DRAFT_MATERIALIZATION' | 'MAINTENANCE' | 'SCIENTIFIC_WORKFLOW' | 'CREATE_INITIAL_REVISION' | 'EXISTING_FALLBACK';
export type RouteMetrics = {
 routeSelections: Record<RouteMetricStage, number>;
 bypassedStageSelections: Record<RouteMetricStage, number>;
};
export type LifecycleMetricKind='withdrawal_committed'|'withdrawal_rejected'|'restore_committed'|'restore_rejected';
export type LifecycleOperationalMetrics=Record<LifecycleMetricKind,number>;
// Finding M8, decided: a `scientificMetrics` block (seven counters: entry, blocked,
// recovery_required, materialization_blocked, materialization_recovery_required,
// materialization_retry, recovery_diagnostic) used to live here, incremented by
// `recordScientificMetric`. That function had exactly one occurrence repo-wide -- its
// own definition -- with no production caller and no test, ever. The seven counters
// therefore initialised to 0 and were STRUCTURALLY UNABLE to become anything else,
// yet shipped inside every `self-audit.ts` result as `metrics`, which both hosts'
// SKILL.md tell the agent to read. A permanently-zero block that looks like signal is
// worse than no block: `recordLifecycleMetric` right below is the proof this shape
// works when it is real (2 production call sites, 2 tests asserting its counters).
// Decision: removed rather than wired to invented call sites, because placing seven
// counters at "the right" semantic points in the runtime is a real design question
// this fix cannot answer by guessing -- a wrong placement would still be false
// signal, just no longer visibly zero. If real producers are ever designed for this,
// they belong back here WITH the call sites and tests `recordLifecycleMetric` has.
export type RuntimeMetrics={currentParallelValidators:number;maxObservedParallelValidators:number;totalValidatorTasks:number;validatorFailures:number;currentModelCalls:number;maxObservedParallelModelCalls:number;totalModelCalls:number;currentWrites:number;maxObservedParallelWrites:number;totalWrites:number;currentPlannerCalls:number;totalPlannerCalls:number;currentRoleCalls:number;totalRoleCalls:number;totalTutorCalls:number;totalReviewerCalls:number;totalMutations:number;rebuildAttempts:number;rebuildFailures:number;routeMetrics:RouteMetrics;lifecycleMetrics:LifecycleOperationalMetrics};

// Every member of `RouteMetricStage`, and the type is the source of truth for that.
// `CREATE_INITIAL_REVISION` was missing here while `proposal-workspace.ts` routes every
// initial-revision operation through it, so `routeSelections[stage]++` incremented an
// absent key: `undefined++` is NaN, and NaN++ stays NaN for the life of the process.
const routeStages: RouteMetricStage[] = ['LIFECYCLE', 'DIRECT_DOCUMENT', 'CHAT_DELIBERATION', 'DRAFT_MATERIALIZATION', 'MAINTENANCE', 'SCIENTIFIC_WORKFLOW', 'CREATE_INITIAL_REVISION', 'EXISTING_FALLBACK'];
function emptyRouteCounts(): Record<RouteMetricStage, number> {
 return Object.fromEntries(routeStages.map(stage => [stage, 0])) as Record<RouteMetricStage, number>;
}
function emptyRouteMetrics(): RouteMetrics {
 return {routeSelections: emptyRouteCounts(), bypassedStageSelections: emptyRouteCounts()};
}
function emptyLifecycleMetrics(): LifecycleOperationalMetrics { return {withdrawal_committed:0,withdrawal_rejected:0,restore_committed:0,restore_rejected:0}; }
function emptyMetrics(): RuntimeMetrics {
 return {currentParallelValidators:0,maxObservedParallelValidators:0,totalValidatorTasks:0,validatorFailures:0,currentModelCalls:0,maxObservedParallelModelCalls:0,totalModelCalls:0,currentWrites:0,maxObservedParallelWrites:0,totalWrites:0,currentPlannerCalls:0,totalPlannerCalls:0,currentRoleCalls:0,totalRoleCalls:0,totalTutorCalls:0,totalReviewerCalls:0,totalMutations:0,rebuildAttempts:0,rebuildFailures:0,routeMetrics:emptyRouteMetrics(),lifecycleMetrics:emptyLifecycleMetrics()};
}
let metrics:RuntimeMetrics=emptyMetrics();

export function resetRuntimeMetrics(){metrics=emptyMetrics()}
export function getRuntimeMetrics():RuntimeMetrics{return {...metrics,routeMetrics:{routeSelections:{...metrics.routeMetrics.routeSelections},bypassedStageSelections:{...metrics.routeMetrics.bypassedStageSelections}},lifecycleMetrics:{...metrics.lifecycleMetrics}}}
export function recordRouteMetric(stage: RouteMetricStage, bypassedStages: readonly RouteMetricStage[]): void {
 metrics.routeMetrics.routeSelections[stage]++;
 for (const bypassedStage of bypassedStages) metrics.routeMetrics.bypassedStageSelections[bypassedStage]++;
}
export async function validationTask<T>(run:()=>T|Promise<T>):Promise<T>{if(metrics.currentParallelValidators>=LIMITS.maxParallelValidationTasks)throw new Error('VALIDATION_PARALLELISM_LIMIT');metrics.currentParallelValidators++;metrics.maxObservedParallelValidators=Math.max(metrics.maxObservedParallelValidators,metrics.currentParallelValidators);metrics.totalValidatorTasks++;try{await Promise.resolve();return await run()}catch(error){metrics.validatorFailures++;throw error}finally{metrics.currentParallelValidators--}}
// Ambient-model paradigm (design `sdd/proposal-deliberation-ambient-model`, SLICE 2): the
// `currentModelCalls>=LIMITS.maxParallelModelCalls` throttle (a real-API-cost cap) was
// removed -- role-port invocations (ambient-echoed or scripted-test-injected) are no
// longer real network calls to bound. The counting itself STAYS: `modelCalls`/
// `plannerCalls`/`tutorCalls`/`reviewerCalls` are still real, observable result fields
// many tests assert on.
export async function modelCall<T>(kind:'planner'|'tutor'|'reviewer',run:()=>Promise<T>):Promise<T>{metrics.currentModelCalls++;metrics.maxObservedParallelModelCalls=Math.max(metrics.maxObservedParallelModelCalls,metrics.currentModelCalls);metrics.totalModelCalls++;if(kind==='planner'){metrics.currentPlannerCalls++;metrics.totalPlannerCalls++}else{metrics.currentRoleCalls++;metrics.totalRoleCalls++;if(kind==='tutor')metrics.totalTutorCalls++;else metrics.totalReviewerCalls++}try{return await run()}finally{metrics.currentModelCalls--;if(kind==='planner')metrics.currentPlannerCalls--;else metrics.currentRoleCalls--}}
export async function writeTask<T>(run:()=>Promise<T>):Promise<T>{if(metrics.currentWrites>=LIMITS.maxParallelWriteTasks)throw new Error('WRITE_PARALLELISM_LIMIT');metrics.currentWrites++;metrics.maxObservedParallelWrites=Math.max(metrics.maxObservedParallelWrites,metrics.currentWrites);try{const result=await run();metrics.totalWrites++;return result}finally{metrics.currentWrites--}}
export function recordLifecycleMetric(kind:LifecycleMetricKind){metrics.lifecycleMetrics[kind]++}
export function recordMutation(){metrics.totalMutations++}
export function recordRebuildAttempt(){metrics.rebuildAttempts++}
export function recordRebuildFailure(){metrics.rebuildFailures++}
