"""Offline HTTP release matrix. No credentials, external requests, or bookings.

Covers source-backed catalog journeys and transcript filters. Browser network
image failures and assistive technology behavior still require browser checks.
"""
import json
import time
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from backend.main import create_app
from live_e2e import CASES, check_response


class ReleaseAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.settings = patch('backend.main.load_settings', return_value={'OPENAI_API_KEY': ''})
        self.settings.start()
        self.addCleanup(self.settings.stop)
        # A regression that accidentally selects the remote runtime fails locally.
        self.remote = patch('httpx.AsyncClient.send', side_effect=AssertionError('No external inference in offline acceptance'))
        self.remote.start()
        self.addCleanup(self.remote.stop)
        self.client = TestClient(create_app(offline_catalog=True))
        self.addCleanup(self.client.close)

    def chat(self, message, transcript=()):
        start = time.monotonic()
        result = self.client.post('/chat', json={'message': message, 'transcript': list(transcript)})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertLess(time.monotonic() - start, 2.0, 'Local grounded catalog exceeded 2 second acceptance budget')
        return result.json()

    @staticmethod
    def ids(body):
        return [car['id'] for block in body['blocks'] if block.get('component') == 'CarList'
                for car in block['props']['cars']]

    def test_catalog_journeys_offline(self):
        for case, (message, history) in CASES.items():
            with self.subTest(case=case):
                transcript = [{'role': 'user', 'content': item} for item in history]
                body = self.chat(message, transcript)
                self.assertEqual(check_response(case, 200, body), [])

    def test_configured_api_standard_journeys_do_not_use_network(self):
        with patch('backend.main.load_settings', return_value={
            'OPENAI_API_KEY': 'fixture-not-a-real-key', 'OPENAI_MODEL': 'fixture-model'
        }):
            self.test_catalog_journeys_offline()
            self.test_repeated_transcript_followup_retains_budget_and_powertrain()

    def test_unfamiliar_question_keeps_model_adapter(self):
        response = {'status': 'completed', 'output': [{
            'type': 'message', 'role': 'assistant', 'content': [{
                'type': 'output_text', 'text': json.dumps({'sections': ['What does your commute involve?']})
            }]
        }]}
        with patch('backend.main.load_settings', return_value={
            'OPENAI_API_KEY': 'fixture-not-a-real-key', 'OPENAI_MODEL': 'fixture-model'
        }), patch('backend.openai_runtime.OpenAIRuntime._request', new_callable=AsyncMock, return_value=response) as adapter:
            with TestClient(create_app()) as client:
                body = client.post('/chat', json={'message': 'How would a Mazda suit my unusual commute?'}).json()
            self.assertEqual(body['blocks'], [{'id': 'block-0', 'type': 'text', 'role': 'answer', 'text': 'What does your commute involve?'}])
            self.assertGreaterEqual(adapter.await_count, 1)

    def test_repeated_transcript_followup_retains_budget_and_powertrain(self):
        transcript = [{'role': 'user', 'content': 'Show me Mazda SUVs under $60,000.'},
                      {'role': 'assistant', 'content': 'CX-5, CX-90 Inline 6 Turbo and CX-90 Plug-in Hybrid match.'}]
        for message in ['Which of those is a plug-in hybrid?', 'Show those again', 'And those under $55,000?']:
            with self.subTest(message=message):
                body = self.chat(message, transcript)
                self.assertEqual(self.ids(body), ['us-2027-cx90-phev'])
                if '55,000' in message:
                    cars = [car for block in body['blocks'] if block.get('component') == 'CarList' for car in block['props']['cars']]
                    self.assertTrue(all(trim['msrp'] < 55000 for car in cars for trim in car['trims']))
                transcript.extend([{'role': 'user', 'content': message}, {'role': 'assistant', 'content': 'CX-90 Plug-in Hybrid matches.'}])

    def test_explicit_new_selection_resets_prior_filters(self):
        transcript = [{'role': 'user', 'content': 'Show SUVs under $35,000'},
                      {'role': 'assistant', 'content': 'CX-5 matches.'},
                      {'role': 'user', 'content': 'Tell me about CX-90 plug-in hybrid'}]
        body = self.chat('Show me Mazda3 hatchbacks', transcript)
        self.assertEqual(self.ids(body), ['us-2027-mazda3'])

    def test_media_copy_uses_captions_and_preserves_raw_source(self):
        body = self.chat('Show photos of CX-5')
        gallery = next(block for block in body['blocks'] if block.get('component') == 'VehicleGallery')
        text = gallery['fallback_text']
        records = gallery['props']['records']
        from backend.catalog import Catalog
        from backend.main import project_root
        expected = Catalog(project_root / 'data/mazda/us/2027').get_vehicle_media('us-2027-cx5')['records']
        self.assertEqual(records, expected)
        self.assertIn('configuration labels', text)
        self.assertNotIn('source', text.lower())
        self.assertNotIn('cloth/leather look', text)

    def test_verified_rotation_and_missing_mesh_remain_distinct(self):
        body = self.chat('Show the CX-5 in 3D')
        component = next(block for block in body['blocks'] if block.get('component') == 'VehicleVisualization')
        from backend.main import project_root
        verified = []
        for record in component['props']['records']:
            for visualization in record['visualizations']:
                self.assertFalse(visualization['model_3d_url'])
                if visualization['status'] == 'verified_frames':
                    verified.append(visualization)
                    frames = json.loads(visualization['frame_urls_json'])
                    self.assertEqual(len(frames), 48)
                    self.assertEqual(len(set(frames)), 48)
                    for frame in frames:
                        self.assertTrue(frame.startswith('/assets/vehicle-rotations/'))
                        self.assertNotIn('..', frame)
                        asset = project_root / 'frontend' / frame.lstrip('/')
                        data = asset.read_bytes()
                        self.assertEqual(data[:4], b'RIFF')
                        self.assertEqual(data[8:12], b'WEBP')
                else:
                    self.assertIn(visualization['frame_urls_json'], ('', '[]'))
        self.assertGreaterEqual(len(verified), 1)
        original = next(row for row in verified if row['visualization_id'] == '27CX525S-51K')
        self.assertEqual(original['product_trim_code'], '27CX525S')
        self.assertEqual(original['color_code'], '51K')
        self.assertTrue(component['fallback_text'])
        # Missing configurations retain unavailable states; no mesh is fabricated.
        result = self.client.post('/catalog/presentation', json={
            'tool_name': 'render_vehicle_gallery', 'arguments': {'model_id': 'unknown'}})
        self.assertEqual(result.status_code, 422)
        self.assertIn('unavailable', result.json()['detail'])


if __name__ == '__main__':
    unittest.main()
