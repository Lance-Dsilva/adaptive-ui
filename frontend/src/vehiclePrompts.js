export function isFullFeatureComparison(question) {
  return /\b(?:all|every|full|complete)\s+(?:features?|specs?|specifications?|equipment)\b|\b(?:full|complete)\s+(?:vehicle\s+)?comparison\b/i.test(question);
}

export const fuelEconomyRequest = /\b(?:mpg|mpge|fuel economy|fuel efficiency|(?:gas )?mileage)\b/i;
export const engineFeaturesRequest = /\bengines?\s+(?:features?|equipment)\b/i;
const engineTopic = /\bengine (?:details?|specs?|specifications?|and mechanical)\b/i;
const vehicleReference = /\b(?:cx|mx)[\s\-‐‑–]?\d+\b|\bmazda\s*\d+\b|\b20\d{2}\b|\b\d\.\d+\s+(?:s\b|turbo\b)|\b(?:other|different|new)\s+(?:trim|configuration|model|cars?)\b/i;

export function isEngineComparison(question) {
  return engineTopic.test(question) || engineFeaturesRequest.test(question) ||
    /^(?:engine|engines|compare (?:the |their )?engines?)[.!?]*$/i.test(question.trim()) ||
    (fuelEconomyRequest.test(question) && /\bengines? and\b/i.test(question));
}

export function comparisonFollowup(question, blocks) {
  const target = question.toLowerCase().trim()
    .replace(/^(?:(?:can|could|would) you\s+|please\s+)?(?:compare|show(?: me)?|list|view)\s+(?:(?:the|their)\s+)?/, '')
    .replace(/[.!?]+$/, '')
    .replace(/\s+(?:for|on)\s+(?:both|these|those)(?:\s+(?:vehicles|cars|models))?$/, '');
  if (vehicleReference.test(target)) return null;
  const engine = /^(?:(?:all|every|full|complete)\s+)?engines?(?:\s+(?:details?|specs?|specifications?|features?|equipment|and mechanical))?(?:$|\s+(?:like|including|and|with)\b)/.test(target);
  const engineFocus = engineFeaturesRequest.test(target) ? 'engine features'
    : fuelEconomyRequest.test(target) ? 'engine specs and fuel economy' : 'engine specs';
  const focus = engine ? engineFocus
    : /^(?:all|every|full|complete)\s+(?:features?|specs?|specifications?|equipment|comparison)$/.test(target) ? 'all features'
      : /^(?:mpg|mpge|fuel economy|fuel efficiency|(?:gas )?mileage)$/.test(target) ? 'fuel economy' : null;
  if (!focus) return null;
  const card = blocks?.find(block => block.component === 'CarComparison');
  const trimIds = card?.props?.records?.map(record => record.trim_id);
  if (trimIds?.length !== 2 || !trimIds.every(Boolean) || trimIds[0] === trimIds[1]) return null;
  return { intent: 'comparison', trim_ids: trimIds, focus };
}
