const locks=new Set<string>();
type MutationLockMetrics={activeMutationLocks:number;maxObservedMutationLocksPerKey:Record<string,number>;successfulPublications:number;blockedConcurrentMutations:number;staleMutationBlocks:number};
let metrics:MutationLockMetrics={activeMutationLocks:0,maxObservedMutationLocksPerKey:{},successfulPublications:0,blockedConcurrentMutations:0,staleMutationBlocks:0};
export function mutationLockKey(root:string,lineage:string,filename:string,sha:string){return `${root}\0${lineage}\0${filename}\0${sha}`}
export function resetMutationLockMetrics(){metrics={activeMutationLocks:0,maxObservedMutationLocksPerKey:{},successfulPublications:0,blockedConcurrentMutations:0,staleMutationBlocks:0}}
export function getMutationLockMetrics():MutationLockMetrics{return {activeMutationLocks:metrics.activeMutationLocks,maxObservedMutationLocksPerKey:{...metrics.maxObservedMutationLocksPerKey},successfulPublications:metrics.successfulPublications,blockedConcurrentMutations:metrics.blockedConcurrentMutations,staleMutationBlocks:metrics.staleMutationBlocks}}
export function recordSuccessfulPublication(){metrics.successfulPublications++}
export function recordStaleMutationBlock(){metrics.staleMutationBlocks++}
export async function withMutationLock<T>(key:string,run:()=>Promise<T>):Promise<T>{if(locks.has(key)){metrics.blockedConcurrentMutations++;throw new Error('SOURCE_MUTATION_LOCKED')}locks.add(key);metrics.activeMutationLocks++;metrics.maxObservedMutationLocksPerKey[key]=Math.max(metrics.maxObservedMutationLocksPerKey[key]??0,1);try{return await run()}finally{locks.delete(key);metrics.activeMutationLocks--}}
