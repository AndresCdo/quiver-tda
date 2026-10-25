import type { LocalContext } from './types.js';
export const tutorDecisions=['ACCEPT','ACCEPT_WITH_REVISIONS','PROPOSE_ALTERNATIVE','NEEDS_CLARIFICATION','REJECT_WITH_REASON'] as const;
export type TutorAssessment={decision:typeof tutorDecisions[number];summary:string;mathematicalIssues:string[];notationIssues:string[];assumptionIssues:string[];proposedAlternative?:string;requiredRevisions:string[];unresolvedQuestions:string[];riskLevel:'LOW'|'MEDIUM'|'HIGH';affectedEntryIds:string[]};
export type TutorAdapter={assess(input:{instruction:string;context:LocalContext}):Promise<TutorAssessment>};
export function validateTutorAssessment(value:TutorAssessment,allowed:string[]){if(!tutorDecisions.includes(value.decision)||value.affectedEntryIds.some(id=>!allowed.includes(id)))throw new Error('INVALID_TUTOR_ASSESSMENT');return value;}
