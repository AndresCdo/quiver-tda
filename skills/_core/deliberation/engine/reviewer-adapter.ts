import type { LocalContext } from './types.js';
export const reviewerDecisions=['APPROVE','APPROVE_WITH_CHANGES','BLOCK','NEEDS_CLARIFICATION'] as const;
export type ReviewerAssessment={decision:typeof reviewerDecisions[number];scientificCoherence:string;scopeCompliance:string;unsupportedClaims:string[];referenceRisks:string[];notationRisks:string[];requiredChanges:string[];unresolvedQuestions:string[];riskLevel:'LOW'|'MEDIUM'|'HIGH'};
export type ReviewerAdapter={review(input:{instruction:string;context:LocalContext;plan?:unknown}):Promise<ReviewerAssessment>};
export function validateReviewerAssessment(value:ReviewerAssessment){if(!reviewerDecisions.includes(value.decision))throw new Error('INVALID_REVIEWER_ASSESSMENT');return value;}
