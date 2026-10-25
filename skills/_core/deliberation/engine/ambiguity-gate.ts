import type { TargetCandidate } from './types.js';
export function ambiguityGate(candidates:TargetCandidate[]){
 if(!candidates.length)return {blocked:true,status:'ambiguous' as const,question:'No encontré un objetivo. Indicá la sección, etiqueta o un fragmento distintivo.',candidates:[]};
 const [first,second]=candidates;
 if(second&&first.score-second.score<=4){
  // Terms every candidate matched carry no discriminating power; naming them
  // turns an opaque menu into an error the caller can act on, because the fix
  // is to drop them, never to add more words.
  const shared=(first.matchedTerms??[]).filter(term=>candidates.every(c=>(c.matchedTerms??[]).includes(term)));
  const hint=shared.length?`\n\nLos términos ${shared.map(t=>`"${t}"`).join(', ')} coinciden con todos los candidatos y no discriminan: repetí la consulta sin ellos, dejando solo palabras distintivas — sin palabras vacías, sin puntuación, sin número de sección y con las tildes tal como aparecen en el encabezado.`:'';
  // A heading locus names its level marks and its real ancestor path, so two
  // `### Setup` sections, or a section and the subsection inside it, read as
  // different candidates. When one candidate spans another, say how to name
  // the outer one: by its level marks.
  const label=(c:TargetCandidate)=>c.headingLevel?`${'#'.repeat(c.headingLevel)} ${(c.headingPath??[]).join(' › ')}`:((c.headingPath??[]).join(' › ') || c.type);
  const nested=candidates.some(outer=>candidates.some(inner=>inner!==outer&&outer.composite&&inner.composite&&inner.composite.startByte>=outer.composite.startByte&&inner.composite.endByte<=outer.composite.endByte));
  const outerHint=nested?'\n\nOne candidate contains another. To name the outer section, open the query with its level marks, e.g. `## <heading>`; to name the inner one, use its own heading words.':'';
  return {blocked:true,status:'ambiguous' as const,question:`Seleccioná un objetivo:\n${candidates.map((c,i)=>`${i+1}. ${label(c)}: ${c.shortPreview??''}`).join('\n')}${hint}${outerHint}`,candidates};
 }
 return {blocked:false,status:'resolved' as const,candidate:first,candidates:[first]};
}
