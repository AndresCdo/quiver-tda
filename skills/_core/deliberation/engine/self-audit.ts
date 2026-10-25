import { hasActivePendingAuditLifecycleOperation, runConsistencyAudit } from './consistency-audit.js';
import { getMutationLockMetrics } from './mutation-lock.js';
import { getRuntimeMetrics } from './runtime-metrics.js';
import type { PendingAuditContext } from './types.js';

export async function runProposalDeliberationSelfAudit(input:{projectRoot:string;strict?:boolean;runtimeSnapshot?:any;auditContext?:PendingAuditContext}) {
  const consistency=await runConsistencyAudit({projectRoot:input.projectRoot,auditContext:input.auditContext});
  const locks=getMutationLockMetrics();
  const runtime=input.runtimeSnapshot??{};
  const checks:any[]=[];
  checks.push({id:'consistency',status:consistency.status,category:'persistence',evidence:consistency,details:consistency.failures.join(', ')});
  const matchingLifecycleOperation=input.auditContext?await hasActivePendingAuditLifecycleOperation({projectRoot:input.projectRoot,auditContext:input.auditContext}):false;
  const lockStatus=input.auditContext?matchingLifecycleOperation:locks.activeMutationLocks===0;
  checks.push({id:'locks-released',status:lockStatus?'PASS':'FAIL',category:'runtime',evidence:{...locks,matchingLifecycleOperation},details:input.auditContext?'pending lifecycle audit must retain its matching lifecycle lock owner':'mutation locks must be released'});
  checks.push({id:'single-runtime',status:runtime.runtimeCount>1?'FAIL':'PASS',category:'runtime',evidence:runtime.runtimeCount??1,details:'runtime snapshot'});
  checks.push({id:'single-orchestrator',status:runtime.orchestratorCount>1?'FAIL':'PASS',category:'runtime',evidence:runtime.orchestratorCount??1,details:'orchestrator snapshot'});
  checks.push({id:'v1-inactive',status:runtime.v1Active?'FAIL':'PASS',category:'runtime',evidence:Boolean(runtime.v1Active),details:'V1 must be inactive'});
  const criticalFailures=checks.filter((check:any)=>check.status==='FAIL').map((check:any)=>check.id);
  const warned=checks.filter((check:any)=>check.status==='WARN').length;
  const passed=checks.filter((check:any)=>check.status==='PASS').length;
  return {status:criticalFailures.length?'FAIL':warned?'WARN':'PASS',runtimeStatus:criticalFailures.length?'FAIL':'PASS',editorialStatus:'WARN',checks,summary:{passed,warned,failed:criticalFailures.length},criticalFailures,metrics:getRuntimeMetrics()};
}
