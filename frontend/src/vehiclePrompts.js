const wording = {
  details: 'Show me details about',
  colors: 'I want to choose a color for',
  photos: 'Show me photos of',
  rotation: 'Show me a 360° view of',
  financing: 'Show me published financing information for',
};

export function isFullFeatureComparison(question) {
  return /\b(?:all|every|full|complete)\s+(?:features?|specs?|specifications?|equipment)\b|\b(?:full|complete)\s+(?:vehicle\s+)?comparison\b/i.test(question);
}

export function fullFeatureFollowup(question, blocks) {
  const target = question.toLowerCase().trim()
    .replace(/^(?:compare|show(?: me)?|list|view)\s+(?:the\s+)?/, '')
    .replace(/[.!?]+$/, '')
    .replace(/\s+(?:for|on)\s+(?:both|these|those)(?:\s+(?:vehicles|cars|models))?$/, '');
  if (!/^(?:all|every|full|complete)\s+(?:features?|specs?|specifications?|equipment|comparison)$/.test(target)) return null;
  const card = blocks?.find(block => block.component === 'CarComparison');
  const trimIds = card?.props?.records?.map(record => record.trim_id);
  if (trimIds?.length !== 2 || !trimIds.every(Boolean) || trimIds[0] === trimIds[1]) return null;
  return { intent: 'comparison', trim_ids: trimIds, focus: 'all features' };
}

export function askAboutVehicle(intent, vehicle, trim, color) {
  const model = vehicle.name.replace(/^Mazda\s+(?=Mazda)/i, '');
  const subject = [vehicle.model_year || vehicle.year, model, trim?.name].filter(Boolean).join(' ');
  const message = color
    ? color.location === 'interior'
      ? `Show me the ${color.name} interior of the ${subject}.`
      : `Show me the ${subject} in ${color.name}.`
    : `${wording[intent]} the ${subject}.`;
  window.dispatchEvent(new CustomEvent('shopping-prompt', { detail: {
    message,
    vehicleAction: {
      intent: color ? 'color_preview' : intent,
      model_id: vehicle.model_id || vehicle.id,
      trim_id: trim?.trim_id,
      color_id: color?.color_id,
    },
  } }));
}

export function askShoppingQuestion(message, compare = false) {
  window.dispatchEvent(new CustomEvent('shopping-prompt', { detail: { message, compare } }));
}

export function askToCompare(picks, focus = '') {
  const descriptions = picks.map(({ car, trim }) => [
    car.year, car.name, trim.name, trim.body_style, trim.drivetrain,
    trim.seating_capacity && `${trim.seating_capacity.replaceAll('|', ' or ')} seats`,
  ].filter(Boolean).join(' '));
  window.dispatchEvent(new CustomEvent('shopping-prompt', { detail: {
    message: `Compare the ${descriptions.join(' with the ')}${focus ? ` on ${focus}` : ''}.`,
    vehicleAction: { intent: 'comparison', trim_ids: picks.map(({ trim }) => trim.trim_id), focus: focus || undefined },
  } }));
}
