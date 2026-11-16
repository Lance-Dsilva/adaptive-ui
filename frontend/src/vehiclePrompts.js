export function isFullFeatureComparison(question) {
  return /\b(?:all|every|full|complete)\s+(?:features?|specs?|specifications?|equipment)\b|\b(?:full|complete)\s+(?:vehicle\s+)?comparison\b/i.test(question);
}

const engineComparisonTarget = /^(?:engine|engines|engine (?:specs?|specifications?|and mechanical)(?: comparison)?)$/i;

export function isEngineComparison(question) {
  return engineComparisonTarget.test(question.trim()) ||
    /\bengine (?:specs?|specifications?)\b/i.test(question) ||
    /\bcompare (?:the |their )?engines?[.!?]*$/i.test(question.trim());
}

export function comparisonFollowup(question, blocks) {
  const target = question.toLowerCase().trim()
    .replace(/^(?:compare|show(?: me)?|list|view)\s+(?:(?:the|their)\s+)?/, '')
    .replace(/[.!?]+$/, '')
    .replace(/\s+(?:for|on)\s+(?:both|these|those)(?:\s+(?:vehicles|cars|models))?$/, '');
  const focus = engineComparisonTarget.test(target) ? 'engine specs'
    : /^(?:all|every|full|complete)\s+(?:features?|specs?|specifications?|equipment|comparison)$/.test(target) ? 'all features' : null;
  if (!focus) return null;
  const card = blocks?.find(block => block.component === 'CarComparison');
  const trimIds = card?.props?.records?.map(record => record.trim_id);
  if (trimIds?.length !== 2 || !trimIds.every(Boolean) || trimIds[0] === trimIds[1]) return null;
  return { intent: 'comparison', trim_ids: trimIds, focus };
}
