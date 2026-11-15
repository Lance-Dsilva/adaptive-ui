import { execFileSync } from 'node:child_process';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { build } from 'esbuild';

const frontend = dirname(fileURLToPath(import.meta.url));
const root = resolve(frontend, '..');
const temporary = await mkdtemp(join(tmpdir(), 'adaptive-ui-components-'));
try {
  const fixturePath = join(temporary, 'fixtures.json');
  execFileSync(join(root, '.venv/bin/python'), ['-c', `
import json
import sys
from pathlib import Path
from backend.registry import ToolRegistry
registry = ToolRegistry(Path.cwd())
fixtures = []
for car in registry.invoke('search_cars', {'model_year': 2027})['records']:
    model_id = car['model_id']
    details = registry.invoke('get_car_details', {'model_id': model_id})['records']
    media = registry.invoke('get_vehicle_media', {'model_id': model_id})['records']
    offers = registry.invoke('get_financing_offers', {
        'model_id': model_id, 'as_of': '2026-11-13',
    })['records']
    for component, records in [
        ('VehicleDetails', details), ('VehicleGallery', media),
        ('ColorOptions', media), ('VehicleVisualization', media),
        ('FinancingOffers', offers),
    ]:
        fixtures.append({'component': component, 'records': records, 'model': model_id})
    comparison = registry.invoke('compare_cars', {
        'trim_ids': [trim['trim_id'] for trim in car['trims'][:2]],
    })['records']
    fixtures.append({'component': 'CarComparison', 'records': comparison, 'model': model_id})
Path(sys.argv[1]).write_text(json.dumps(fixtures))
`, fixturePath], { cwd: root, stdio: 'inherit' });
  const bundlePath = join(temporary, 'components.cjs');
  await build({
    entryPoints: [join(frontend, 'tests/components.test.jsx')],
    bundle: true,
    platform: 'node',
    format: 'cjs',
    jsx: 'automatic',
    outfile: bundlePath,
  });
  execFileSync(process.execPath, [bundlePath, fixturePath], { stdio: 'inherit' });
} finally {
  await rm(temporary, { recursive: true, force: true });
}
