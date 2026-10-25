import { LifecycleService } from './lifecycle-service.js';
import type { LifecycleRevision, WithdrawalRecord, WorkspaceLifecycleState } from './types.js';

type PublicResult =
 | { outcome:'COMMITTED'|'ALREADY_COMMITTED'; inventory:WorkspaceLifecycleState; withdrawalId?:string; withdrawal?:WithdrawalRecord; revision?:LifecycleRevision }
 | { outcome:'REJECTED'|'INCONSISTENT'|'RECOVERY_REQUIRED'; code:string };

type PublicRequest =
 | { operation:'WITHDRAW_REVISION'; requestId:string; revisionId?:string; locator?:string; reason?:string }
 | { operation:'RESTORE_WITHDRAWN_REVISION'; requestId:string; withdrawalId?:string; reference?:string };

/** Public semantic boundary for an explicitly registered lifecycle-v1 workspace. */
export class LifecycleV1PublicRouter {
 constructor(private readonly input:{projectRoot:string;workspaceId:string;service?:LifecycleService}) {}
 private service() { return this.input.service ?? new LifecycleService(this.input.projectRoot); }
 private failure(value:any):PublicResult { return {outcome:value.outcome,code:value.code}; }
 async execute(request:PublicRequest):Promise<PublicResult> {
  const service=this.service();
  if(!await service.hasLifecycleAuthority(this.input.workspaceId).catch(()=>false)) return {outcome:'REJECTED',code:'LIFECYCLE_V1_UNREGISTERED'};
  const inventory=await service.rebuildLifecycleInventory(this.input.workspaceId).catch(()=>undefined);
  if(!inventory) return {outcome:'INCONSISTENT',code:'LIFECYCLE_INVENTORY_INCONSISTENT'};
  if(request.operation==='WITHDRAW_REVISION') {
   const revision=request.revisionId
    ? inventory.revisions.find(item=>item.revisionId===request.revisionId)
    : request.locator ? inventory.revisions.filter(item=>item.locator===request.locator&&item.state==='ACTIVE')[0] : undefined;
   if(!revision) return {outcome:'REJECTED',code:'REVISION_NOT_WITHDRAWABLE'};
   const result=await service.withdrawRevision({workspaceId:this.input.workspaceId,requestId:request.requestId,revisionId:revision.revisionId,reason:request.reason});
   return result.outcome==='COMMITTED'||result.outcome==='ALREADY_COMMITTED'
    ? {outcome:result.outcome,inventory:result.inventory,withdrawalId:result.withdrawal?.withdrawalId,withdrawal:result.withdrawal}
    : this.failure(result);
  }
  const result=await service.restoreWithdrawnRevision({workspaceId:this.input.workspaceId,requestId:request.requestId,withdrawalId:request.withdrawalId,reference:request.reference});
  return result.outcome==='COMMITTED'||result.outcome==='ALREADY_COMMITTED'
   ? {outcome:result.outcome,inventory:result.inventory,withdrawal:result.withdrawal,revision:result.revision}
   : this.failure(result);
 }
}
