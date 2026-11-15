"""Rich UI mappings keep configuration identity and published source values intact."""
import unittest
from copy import deepcopy
from pathlib import Path

from backend.catalog import Catalog
from backend.orchestration import ToolResult
from backend.presentation import _car_props
from backend.ui_registry import UIRegistry

ROOT = Path(__file__).resolve().parents[1]


class RichVehiclePropsTests(unittest.TestCase):
    def setUp(self):
        self.catalog = Catalog(ROOT / 'data/mazda/us/2027')

    def test_discovery_contains_full_exact_configuration_specs_and_sources(self):
        result = self.catalog.search_cars(2027)
        source_ids = {source['source_id'] for source in result['sources']}
        for model in result['records']:
            before = deepcopy(model)
            props = _car_props(model)
            self.assertEqual(model, before)
            if model['model_family'] == 'mazda3':
                self.assertEqual(props['name'], 'Mazda3')
            self.assertEqual(props['specifications'], model['specifications'])
            for config in props['configurations']:
                trim = next(trim for trim in model['trims'] if trim['trim_id'] == config['trim_id'])
                for field, value in trim.items():
                    self.assertEqual(config[field], value)
                expected = self.catalog.get_car_details(model['model_id'], config['trim_id'])['records'][0]['specifications']
                self.assertEqual(config['specifications'], expected)
                self.assertTrue(config['specifications'])
                self.assertTrue(all(spec['source_id'] in source_ids for spec in expected))
            props['configurations'][0]['specifications'][0]['value'] = 'changed UI copy'
            self.assertEqual(model, before)

    def test_config_photos_never_use_another_trim_or_claim_exact_seating(self):
        for model in self.catalog.search_cars(2027)['records']:
            for config in _car_props(model)['configurations']:
                for photo in config['photos']:
                    self.assertTrue(photo.get('reference_model_id') == model['model_id'] or not photo['product_trim_code'] or photo['product_trim_code'] == config['product_trim_code'])
                    self.assertIn('reference image', photo['applicability_label'])
                    raw = next(asset for asset in model['assets'] if asset['asset_id'] == photo['asset_id'])
                    for field, value in raw.items():
                        self.assertEqual(photo[field], value)
                if config['image_url']:
                    asset = next(asset for asset in model['assets'] if asset['url'] == config['image_url'])
                    if config['image_is_reference']:
                        self.assertEqual(asset['reference_model_id'], model['model_id'])
                        self.assertEqual(asset['applicability'], 'model_reference')
                        self.assertIn('may differ', config['image_caption'])
                    else:
                        self.assertIn(asset['product_trim_code'], ('', config['product_trim_code']))
                        self.assertEqual(asset['source_model_year'], model['model_year'])
                        self.assertEqual(asset['model_id'], model['model_id'])


    def test_registry_accepts_rich_props_and_comparison_keeps_all_raw_specifications(self):
        result = self.catalog.search_cars(2027)
        renderer = UIRegistry(ROOT)
        rendered = renderer.render('render_car_list', ToolResult('search', 'search_cars', {}, result), [0, 1], 'Original text')
        self.assertIn('configurations', rendered['props']['cars'][0])
        selected = [model['trims'][0]['trim_id'] for model in result['records']]
        compared = self.catalog.compare_cars(selected)
        for record in compared['records']:
            expected = self.catalog.get_car_details(record['model_id'], record['trim_id'])['records'][0]
            self.assertEqual(record['specifications'], expected['specifications'])
            self.assertEqual(record['assets'], expected['assets'])
            for field in ('destination_usd', 'seating_rows', 'seating_capacity', 'transmission'):
                self.assertEqual(record[field], expected['trims'][0][field])


    def test_explicit_reference_links_only_and_exact_images_preferred(self):
        from backend.catalog import _asset_applies
        from backend.presentation import _image_props
        records = self.catalog.search_cars(2027)['records']
        phev = next(model for model in records if model['model_id'] == 'us-2027-cx90-phev')
        cx5 = next(model for model in records if model['model_id'] == 'us-2027-cx5')
        ref = {**cx5['assets'][0], 'model_id': '', 'model_family': 'cx90',
               'reference_model_id': phev['model_id'], 'applicability': 'model_reference',
               'source_model_year': '2026', 'product_trim_code': 'old-2026-code',
               'url': 'https://example.invalid/2026-phev.jpg'}
        self.assertTrue(_asset_applies(ref, phev, phev['trims']))
        self.assertFalse(_asset_applies(ref, cx5, cx5['trims']))
        self.assertFalse(_asset_applies({**ref, 'reference_model_id': ''}, phev, phev['trims']))
        self.assertFalse(_asset_applies({**ref, 'model_id': 'us-2027-cx90-mhev'}, phev, phev['trims']))
        mapped = _car_props({**phev, 'assets': [ref]})
        self.assertTrue(mapped['image_is_reference'])
        self.assertIn('2026', mapped['image_caption'])
        self.assertIn('2027 model may differ', mapped['image_caption'])
        hero = {**ref, 'model_id': phev['model_id'], 'reference_model_id': '',
                'source_model_year': '2027', 'product_trim_code': '', 'url': 'https://example.invalid/hero.jpg'}
        image = _image_props({**phev, 'assets': [ref, hero]})
        self.assertEqual(image['image_url'], hero['url'])
        self.assertFalse(image['image_is_reference'])
        self.assertIn('trim unspecified', image['image_caption'])

    def test_phev_reference_photos_follow_exact_trim(self):
        model_id = 'us-2027-cx90-phev'
        model = self.catalog.get_vehicle_media(model_id)['records'][0]
        self.assertEqual(len(model['trims']), 3)
        for trim in model['trims']:
            with self.subTest(trim=trim['name']):
                record = self.catalog.get_vehicle_media(model_id, trim['trim_id'])['records'][0]
                photos = [asset for asset in record['assets'] if asset.get('reference_model_id')]
                defaults = [asset for asset in photos if not asset['color_code']]
                self.assertEqual(len(defaults), 1)
                self.assertTrue(all(asset['reference_trim_id'] == trim['trim_id'] for asset in photos))
                self.assertTrue(all(asset['source_model_year'] == '2026' for asset in photos))
                paint_codes = {asset['color_code'] for asset in photos if asset['color_code']}
                published = {color['color_code'] for color in record['colors'] if color['location'] == 'exterior'}
                self.assertEqual(paint_codes, published - {'52M', '52C'})
                red = next(asset for asset in photos if asset['color_code'] == '46V')
                self.assertIn('Soul-Red-front.png', red['url'])
                self.assertEqual(red['fetch_status'], 'http_200_get_image_verified')
