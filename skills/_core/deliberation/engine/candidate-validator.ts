import { buildStructuralIndex } from './document-index.js'; import { declaredValues,citedValues } from './reference-index.js'; import { buildSymbolIndex } from './symbol-index.js'; import { buildConceptIndex } from './concept-index.js'; import { sha256,type Compilation,type DocumentState,type EditPlan } from './types.js'; import { validationTask } from './runtime-metrics.js'; import { atoms as preservationAtoms,delta as preservationDelta,violations as preservationViolations } from './preservation.js'; import { DOMAIN } from './domain-profile.js'; import { successorCandidateRefusal } from './proposal-workspace.js';
export async function validateCandidate(state:DocumentState,plan:EditPlan,compiled:Compilation){
 const source=compiled.candidate;const structural=buildStructuralIndex(source);const [symbols,concepts,markdown,displayDelimiters,declared,cited]=await Promise.all([validationTask(()=>buildSymbolIndex(source,structural)),validationTask(()=>buildConceptIndex(source,structural)),validationTask(()=>!/^#{7,}/m.test(source)),validationTask(()=>(source.match(/^\$\$$/gm)?.length??0)%2===0),validationTask(()=>declaredValues(source)),validationTask(()=>citedValues(source))]);
 // Reference integrity (change 5, domain-neutral). What DECLARES a numbered/named thing and
 // what CITES it are `profile.references.{declares,cites}` lookups now -- never a hardwired
 // `\label`/`\tag`/`\eqref`/`(Ec. N)` assumption. A document where the profile's vocabulary
 // finds nothing to declare or cite reports `referencesApplicable:false` -- "not applicable",
 // never folded into the same shape as a confirmed-consistent check.
 const [declarationsUnique,referencesOk]=await Promise.all([validationTask(()=>declared.length===new Set(declared).size),validationTask(()=>{const known=new Set(declared);return cited.every(value=>known.has(value))})]);
 const referencesApplicable=declared.length>0||cited.length>0;
 const action=plan.actions[0];let operationOk=true;if(action&&(action.kind==='move'||action.kind==='copy')){const sourceEntry=state.structuralIndex.byId[action.sourceEntryIds[0]];const original=sourceEntry?state.documentBytes.subarray(sourceEntry.startByte,sourceEntry.endByte):Buffer.alloc(0);const inserted=action.moveMode==='ADAPTIVE'?Buffer.from(action.transformedContent??''):original;const occurrences=(needle:Buffer)=>{let count=0,at=0;while(needle.length){const found=Buffer.from(source).indexOf(needle,at);if(found<0)break;count++;at=found+needle.length;}return count};if(action.moveMode==='LITERAL'){const count=occurrences(original);operationOk=action.kind==='move'?count===1:count===2;}else{operationOk=inserted.length>0&&source.includes(inserted.toString('utf8'));}if(sourceEntry?.type==='section'||sourceEntry?.type==='subsection')operationOk=operationOk&&source.includes(original.toString('utf8').match(/^#+[^\n]*/)?.[0]??'');}
 // Preservation gate (change 4, domain-neutral). Canonical form is never an
 // intentional change, so it joins `ok` and blocks outright. The delta is data,
 // not a verdict: the caller has to SEE what disappeared before it can
 // acknowledge it, so the accept gate lives in the orchestrator, which knows
 // preview from publish. `mathDelta`/`mathViolations` are PERMANENT legacy
 // aliases for `preservationDelta`/`preservationViolations` -- never removed,
 // so the mathematical SKILL.md never needs an edit.
 const violationsList=await validationTask(()=>preservationViolations(source));
 const beforeAtoms=await validationTask(()=>preservationAtoms(state.documentBytes.toString('utf8')));
 const applicable=beforeAtoms.size>0;
 const deltaResult=await validationTask(()=>preservationDelta(state.documentBytes.toString('utf8'),source));
 const canonicalForm=!violationsList.length;
 // Source authority (change 9, domain-neutral, off by default). Unlike preservation/reference
 // integrity, a conflict never fails `ok` here -- even a `severity:'refuse'` profile's hard
 // block is the ORCHESTRATOR's own gate (mirroring where the preservation accept-gate lives),
 // so this validator stays a pure report, never a verdict.
 const sourceAuthorityConflicts=await validationTask(()=>DOMAIN.sourceAuthority?DOMAIN.sourceAuthority.detectConflicts(source):[]);
 // Publication parity. Every candidate this validator passes is published through
 // `derive_successor`, whose own pre-publish validation (patch manifest, composition, display
 // blocks, standalone ATX headings, flat-domain definitions, size and reserved bytes) used to run
 // only on the accept turn -- so a preview could answer `awaiting_acceptance` for a candidate the
 // accept turn was certain to refuse. The same function now runs here, over the same source
 // bytes, digest and patches the accept turn sends, and its refusal blocks the preview with the
 // accept turn's own code. A document without the artifact marker is not a managed revision and
 // reports `prePublishApplicable:false`, never a pass.
 const prePublish=await validationTask(()=>successorCandidateRefusal(state.documentBytes.toString('utf8'),state.documentSha256,compiled.patches));
 const prePublishOk=prePublish.refusal===null;
 const candidateSha=sha256(source);const scope=compiled.unchangedByteCoverage&&candidateSha===compiled.candidateSha256;
 return {
  ok:markdown&&displayDelimiters&&declarationsUnique&&referencesOk&&!symbols.conflicts.length&&scope&&operationOk&&canonicalForm&&prePublishOk,
  prePublishApplicable:prePublish.applicable,candidateValidation:prePublish.refusal,
  mathDelta:deltaResult,preservationDelta:deltaResult,preservationApplicable:applicable,
  mathViolations:violationsList,preservationViolations:violationsList,
  referencesApplicable,
  sourceAuthorityConflicts,
  results:{markdown,displays:displayDelimiters,declarations:declarationsUnique,references:referencesOk,symbols:!symbols.conflicts.length,concepts:!!concepts,scope,unchangedByteCoverage:compiled.unchangedByteCoverage,candidateSha:candidateSha===compiled.candidateSha256,operation:operationOk,preservationCanonicalForm:canonicalForm,preservationPass:!deltaResult.lost.length,prePublish:prePublishOk},
 };
}
