const vehicleLabels = {
  details: 'Details',
  colors: 'Colors & materials',
  photos: 'Photos',
  rotation: '360° view',
  financing: 'Financing',
};

export function browseRequest(filters = {}, { compare = false, focus, priority } = {}) {
  return { intent: 'browse', filters, compare, focus, priority };
}

export function runCatalogAction(label, request) {
  window.dispatchEvent(new CustomEvent('catalog-action', { detail: { label, request } }));
}

export function openVehicle(intent, vehicle, trim, color) {
  const name = vehicle.name.replace(/^Mazda\s+(?=Mazda)/i, '');
  const subject = [vehicle.model_year || vehicle.year, name, trim?.name].filter(Boolean).join(' ');
  runCatalogAction([subject, color?.name || vehicleLabels[intent]].filter(Boolean).join(' · '), {
    intent: color ? 'color_preview' : intent,
    model_id: vehicle.model_id || vehicle.id,
    trim_id: trim?.trim_id,
    color_id: color?.color_id,
  });
}

export function compareVehicles(picks, focus = '') {
  const names = picks.map(({ car, trim }) => [car.name, trim.name].filter(Boolean).join(' '));
  runCatalogAction(`Compare ${names.join(' and ')}`, {
    intent: 'comparison',
    trim_ids: picks.map(({ trim }) => trim.trim_id),
    focus: focus || undefined,
  });
}
