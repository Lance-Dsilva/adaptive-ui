"""HTTP acceptance for visible response semantics and executable follow-ups."""
import copy
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.main import create_app
from backend.response_contract import decorate_response
from live_e2e import validate_blocks


class ResponseContractTests(unittest.TestCase):
    def test_visible_copy_omits_attribution_and_keeps_facts(self):
        blocks = [
            {'type': 'text', 'text': '[source] Mazda | https://example.invalid/spec'},
            {'type': 'text', 'text': 'This trim starts at $39,700 (source: Mazda). Checked Nov 14, 2026.'},
            {'type': 'ui', 'component': 'VehicleDetails',
             'fallback_text': 'Eight seats. Source: Mazda.',
             'props': {'records': [{'source_url': 'https://example.invalid/spec'}]}},
        ]
        result = decorate_response({'blocks': blocks}, 'Show me Mazda details', [])['blocks']
        self.assertEqual(result[0]['text'], 'This trim starts at $39,700.')
        self.assertEqual(result[0]['role'], 'answer')
        self.assertEqual(result[-1]['fallback_text'], 'Eight seats.')
        self.assertEqual(result[-1]['props'], blocks[-1]['props'])

    def setUp(self):
        settings = patch('backend.main.load_settings', return_value={
            'OPENAI_API_KEY': 'fixture-only', 'OPENAI_MODEL': 'fixture-model'})
        settings.start()
        self.addCleanup(settings.stop)
        network = patch('httpx.AsyncClient.send', side_effect=AssertionError('No network allowed'))
        network.start()
        self.addCleanup(network.stop)
        self.client = TestClient(create_app(offline_catalog=True))
        self.addCleanup(self.client.close)

    def chat(self, message, transcript=()):
        response = self.client.post('/chat', json={'message': message, 'transcript': list(transcript)})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(validate_blocks(body), [])
        return body['blocks']

    def test_greeting_is_short_and_actionable_without_api(self):
        for greeting in ['HI', 'hello', 'Hi!']:
            with self.subTest(greeting=greeting):
                blocks = self.chat(greeting)
                self.assertFalse(any(block['type'] == 'ui' for block in blocks))
                answers = [block for block in blocks if block.get('role') == 'answer']
                self.assertEqual(len(answers), 1)
                self.assertLess(len(answers[0]['text']), 180)
                self.assertTrue(any(block.get('role') == 'body' for block in blocks))
                self.assertEqual(sum(len(block['actions']) for block in blocks if block['type'] == 'actions'), 2)
                self.assertTrue(any(block['type'] == 'disclosure' for block in blocks))

    def test_compound_greeting_keeps_vehicle_request(self):
        blocks = self.chat('Hi, show me Mazda SUVs under $35,000')
        cards = [block for block in blocks if block['type'] == 'ui']
        self.assertEqual([car['id'] for block in cards for car in block['props'].get('cars', [])], ['us-2027-cx5'])
        contexts = [block for block in blocks if block['type'] == 'context']
        self.assertTrue(contexts)
        context = ' '.join(item for block in contexts for item in block['items']).lower()
        self.assertIn('suv', context)
        self.assertIn('35,000', context)
        self.assertLess(blocks.index(contexts[0]), blocks.index(cards[0]))
        # Context chips contain text only, never a decorative removal control.
        self.assertTrue(all(isinstance(item, str) for block in contexts for item in block['items']))

    def test_empty_followup_retains_filters_and_clear_budget_is_executable(self):
        transcript = [
            {'role': 'user', 'content': 'Show Mazda SUVs with AWD under $35,000'},
            {'role': 'assistant', 'content': 'CX-5 matches those filters.'},
        ]
        message = 'Which of those is a plug-in hybrid?'
        blocks = self.chat(message, transcript)
        self.assertFalse(any(block['type'] == 'ui' for block in blocks))
        context = ' '.join(item for block in blocks if block['type'] == 'context' for item in block['items']).lower()
        for token in ['suv', 'awd', '35,000']:
            self.assertIn(token, context)
        self.assertTrue('plug' in context or 'phev' in context)
        actions = [action for block in blocks if block['type'] == 'actions' for action in block['actions']]
        clear = next(action for action in actions if 'budget' in action['label'].lower())
        transcript += [{'role': 'user', 'content': message}, {'role': 'assistant', 'content': 'No matches.'}]
        recovered = self.chat(clear['message'], transcript)
        cars = [car for block in recovered if block['type'] == 'ui' for car in block['props'].get('cars', [])]
        self.assertEqual([car['id'] for car in cars], ['us-2027-cx90-phev'])
        self.assertTrue(all(trim['msrp'] > 35000 for car in cars for trim in car['trims']))
        new_context = ' '.join(item for block in recovered if block['type'] == 'context' for item in block['items']).lower()
        self.assertNotIn('35,000', new_context)
        self.assertIn('suv', new_context)
        self.assertIn('awd', new_context)
        # Self-contained action also works with no prior transcript.
        self.assertEqual(self.chat(clear['message']), recovered)

    def test_discovery_with_msrp_suffix_remains_discovery(self):
        for configured in (False, True):
            with self.subTest(configured=configured), patch('backend.main.load_settings', return_value={
                'OPENAI_API_KEY': 'fixture-only' if configured else '', 'OPENAI_MODEL': 'fixture-model'
            }):
                blocks = self.chat('Show me 2027 Mazda SUVs under $40,000 MSRP')
                cards = [block for block in blocks if block['type'] == 'ui']
                self.assertTrue(cards)
                self.assertTrue(all(block['component'] == 'CarList' for block in cards))
                context = ' '.join(item for block in blocks if block['type'] == 'context' for item in block['items'])
                self.assertIn('40,000', context)
                self.assertIn('SUV', context)
                cars = [car for block in cards for car in block['props']['cars']]
                self.assertEqual({car['id'] for car in cars}, {'us-2027-cx5', 'us-2027-cx90-mhev'})
                self.assertTrue(all(trim['msrp'] <= 40000 for car in cars for trim in car['trims']))

    def test_intervening_greeting_preserves_filter_context(self):
        for configured in (False, True):
            with self.subTest(configured=configured), patch('backend.main.load_settings', return_value={
                'OPENAI_API_KEY': 'fixture-only' if configured else '', 'OPENAI_MODEL': 'fixture-model'
            }):
                transcript = [
                    {'role': 'user', 'content': 'Show Mazda SUVs under $35,000'},
                    {'role': 'assistant', 'content': 'CX-5 matches.'},
                    {'role': 'user', 'content': 'Hi'},
                    {'role': 'assistant', 'content': 'Hello!'},
                ]
                blocks = self.chat('Which of those is a plug-in hybrid?', transcript)
                self.assertFalse(any(block['type'] == 'ui' for block in blocks))
                context = ' '.join(item for block in blocks if block['type'] == 'context' for item in block['items'])
                self.assertIn('35,000', context)
                self.assertIn('SUV', context)
                actions = [action for block in blocks if block['type'] == 'actions' for action in block['actions']]
                clear = next(action for action in actions if 'budget' in action['label'].lower())
                recovered = self.chat(clear['message'])
                self.assertEqual([car['id'] for block in recovered if block['type'] == 'ui' for car in block['props'].get('cars', [])], ['us-2027-cx90-phev'])

    def test_fractional_budget_is_not_rounded_to_eligible_price(self):
        for configured in (False, True):
            with self.subTest(configured=configured), patch('backend.main.load_settings', return_value={
                'OPENAI_API_KEY': 'fixture-only' if configured else '', 'OPENAI_MODEL': 'fixture-model'
            }):
                blocks = self.chat('Show Mazda SUVs under $29,989.50')
                self.assertFalse(any(block['type'] == 'ui' for block in blocks))
                context = ' '.join(item for block in blocks if block['type'] == 'context' for item in block['items'])
                self.assertIn('$29,989.50', context)
                self.assertNotIn('$29,990', context)

    def test_block_ids_are_stable_and_unique(self):
        first = self.chat('Show Mazda SUVs under $35,000')
        second = self.chat('Show Mazda SUVs under $35,000')
        self.assertEqual([block['id'] for block in first], [block['id'] for block in second])
        self.assertEqual(len({block['id'] for block in first}), len(first))


class ResponseValidatorTests(unittest.TestCase):
    def test_additive_blocks_reject_malformed_content(self):
        examples = [
            {'type': 'context', 'id': 'ctx', 'items': ['SUV', 'AWD']},
            {'type': 'actions', 'id': 'act', 'actions': [{'id': 'one', 'label': 'View SUVs', 'message': 'Show SUVs', 'compare': False}]},
            {'type': 'disclosure', 'id': 'note', 'title': 'Coverage', 'text': '2027 research snapshot'},
        ]
        self.assertEqual(validate_blocks({'blocks': examples}), [])
        for field, value, index in [('items', [{'label': 'SUV', 'remove': True}], 0), ('items', [], 0),
                                    ('actions', [], 1), ('text', None, 2), ('title', '', 2)]:
            mutated = copy.deepcopy(examples)
            mutated[index][field] = value
            self.assertTrue(validate_blocks({'blocks': mutated}))
        for value in [{'id': 'one', 'label': 'X'}, {'id': 'one', 'label': 'X', 'message': 'Show SUVs', 'compare': 'yes'}]:
            mutated = copy.deepcopy(examples)
            mutated[1]['actions'] = [value]
            self.assertTrue(validate_blocks({'blocks': mutated}))
        duplicated = copy.deepcopy(examples)
        duplicated[1]['id'] = duplicated[0]['id']
        self.assertTrue(validate_blocks({'blocks': duplicated}))
        excessive = copy.deepcopy(examples)
        excessive[1]['actions'] *= 3
        self.assertTrue(validate_blocks({'blocks': excessive}))


class FreshChatTests(unittest.TestCase):
    def test_current_apr_followup_checks_exact_offer_online_for_previous_model(self):
        import json
        import httpx
        from test_openai_runtime import complete

        requests = []
        answer = "I couldn't verify a current 0% APR offer for 60 months on the 2027 CX-5."
        web_reply = {"status": "completed", "output": [
            {"type": "web_search_call", "status": "completed"},
            {"type": "message", "content": [{
                "type": "output_text", "text": answer, "annotations": [
                    {"type": "url_citation", "url": "https://www.mazdausa.com/shopping-tools/special-offers",
                     "end_index": len(answer)},
                ],
            }]},
        ]}

        async def generate(client, url, **kwargs):
            payload = kwargs["json"]
            requests.append(payload)
            return httpx.Response(200, json=web_reply if payload.get("tools") else complete({
                "sections": json.loads(payload["input"])["grounded_sections"],
            }))

        question = "Do they have 0% apr for 60months right now"
        previous = "Show me the 2027 Mazda CX-5."
        with patch("backend.main.load_settings", return_value={
            "OPENAI_API_KEY": "fixture-only", "OPENAI_MODEL": "gpt-6-luna",
        }), patch("httpx.AsyncClient.post", new=generate), TestClient(create_app()) as client:
            web = client.post("/chat", json={
                "message": question, "transcript": [{"role": "user", "content": previous}],
            })
            self.assertEqual(web.status_code, 200)
            self.assertEqual([block["text"] for block in web.json()["blocks"]], [answer])
            recorded = client.post("/chat", json={"message": "Show published financing offers for the 2027 CX-5."})
            self.assertEqual(recorded.status_code, 200)
            self.assertTrue(any(block.get("component") == "FinancingOffers" for block in recorded.json()["blocks"]))

        lookup = requests[0]
        self.assertEqual(lookup["tools"], [{"type": "web_search"}])
        search_input = json.loads(lookup["input"])
        self.assertEqual(search_input["question"], question)
        self.assertEqual(search_input["mentioned_models"], ["cx5"])
        self.assertEqual(search_input["previous_mazda_question"], previous)
        self.assertIn("Verify the rate and term on the same offer", lookup["instructions"])
        self.assertNotIn("tools", requests[1])

    def test_mazda_web_lookup_returns_provider_links_and_catalog_still_returns_cards(self):
        import json
        import httpx
        from test_openai_runtime import complete

        requests = []
        text = "The RX-7 is a Mazda sports car. ([Mazda](https://www.mazda.com/history))"
        lookup = {"status": "completed", "output": [
            {"type": "web_search_call", "status": "completed"},
            {"type": "message", "content": [{
                "type": "output_text", "text": text, "annotations": [
                    {"type": "url_citation", "url": "https://www.mazda.com/history", "end_index": len(text)},
                    {"type": "url_citation", "url": "javascript:void(0)", "end_index": len(text)},
                ],
            }]},
        ]}

        async def generate(client, url, **kwargs):
            payload = kwargs["json"]
            requests.append(payload)
            reply = lookup if payload.get("tools") == [{"type": "web_search"}] else complete({
                "sections": json.loads(payload["input"])["grounded_sections"],
            })
            return httpx.Response(200, json=reply)

        with patch("backend.main.load_settings", return_value={
            "OPENAI_API_KEY": "fixture-only", "OPENAI_MODEL": "gpt-6-luna",
        }), patch("httpx.AsyncClient.post", new=generate), TestClient(create_app()) as client:
            for _ in range(2):
                web = client.post("/chat", json={"message": "When did Mazda launch the RX-7?"})
                self.assertEqual(web.status_code, 200)
                block = web.json()["blocks"][0]
                self.assertEqual(block["text"], "The RX-7 is a Mazda sports car.")
                self.assertEqual(block["citations"], [{"url": "https://www.mazda.com/history", "label": "mazda.com"}])
                self.assertEqual(web.headers["Cache-Control"], "no-store")
            local = client.post("/chat", json={"message": "Show me Mazda SUVs."})
            self.assertEqual(local.status_code, 200)
            self.assertTrue(any(block.get("component") == "CarList" for block in local.json()["blocks"]))

        self.assertEqual(len(requests), 3)
        self.assertTrue(all(request["model"] == "gpt-6-luna" and not request["store"] for request in requests))
        self.assertEqual(requests[0]["tool_choice"], "required")
        self.assertNotEqual(requests[0]["instructions"], requests[1]["instructions"])
        self.assertNotIn("tools", requests[2])

    def test_chat_distinguishes_upstream_timeout_rate_limit_and_rejection(self):
        import httpx

        outcomes = iter((None, 429, 400))

        async def generate(client, url, **kwargs):
            status = next(outcomes)
            if status is None:
                raise httpx.ReadTimeout("fixture")
            return httpx.Response(status)

        with patch("backend.main.load_settings", return_value={
            "OPENAI_API_KEY": "fixture-only", "OPENAI_MODEL": "fixture-model",
        }), patch("httpx.AsyncClient.post", new=generate), TestClient(create_app()) as client:
            for expected in (504, 429, 503):
                response = client.post("/chat", json={"message": "Show me Mazda SUVs."})
                self.assertEqual(response.status_code, expected)
                self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_suv_results_keep_the_list_when_generated_copy_asks_for_a_powertrain(self):
        import json
        import httpx
        from test_openai_runtime import complete

        requests = []

        async def generate(client, url, **kwargs):
            requests.append(kwargs["json"])
            draft = json.loads(kwargs["json"]["input"])["grounded_sections"]
            draft[1] += "\nWhich CX-90 version would you like, mild hybrid or plug-in hybrid?"
            return httpx.Response(200, json=complete({"sections": draft}))

        with patch("backend.main.load_settings", return_value={
            "OPENAI_API_KEY": "fixture-only", "OPENAI_MODEL": "fixture-model",
        }), patch("httpx.AsyncClient.post", new=generate), TestClient(create_app()) as client:
            response = client.post("/chat", json={"message": "Show me Mazda SUVs."})

        self.assertEqual(response.status_code, 200)
        blocks = response.json()["blocks"]
        card = next(block for block in blocks if block.get("component") == "CarList")
        self.assertEqual(len(card["props"]["cars"]), 3)
        self.assertFalse(any(block.get("choice") for block in blocks))
        self.assertIn("Which CX-90", blocks[1]["text"])
        self.assertGreater(blocks.index(card), max(index for index, block in enumerate(blocks) if block["type"] == "text"))
        self.assertEqual(len(requests), 1)

    def test_explicit_trim_choice_needs_one_model_call_and_keeps_both_trim_names(self):
        import json
        import httpx
        from test_openai_runtime import complete

        requests = []

        async def generate(client, url, **kwargs):
            requests.append(json.loads(kwargs["json"]["input"]))
            return httpx.Response(200, json=complete({"sections": ["Which CX-5 trim would you like?"]}))

        with patch("backend.main.load_settings", return_value={
            "OPENAI_API_KEY": "fixture-only", "OPENAI_MODEL": "fixture-model",
        }), patch("httpx.AsyncClient.post", new=generate), TestClient(create_app()) as client:
            response = client.post("/chat", json={
                "message": "Ask me to choose between the 2027 Mazda CX-5 2.5 S and 2.5 S Select before showing details."
            })
        self.assertEqual(response.status_code, 200)
        choice = next(block for block in response.json()["blocks"] if block.get("choice"))
        self.assertEqual([action["label"] for action in choice["actions"]], ["2.5 S", "2.5 S Select"])
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["trims"], ["2.5 S", "2.5 S Select"])

    def test_presenter_turns_cx5_trim_clarification_into_exact_vehicle_actions(self):
        import httpx
        from test_openai_runtime import complete, tool_response

        model = "us-2027-cx5"
        trims = [f"{model}-2-5-s-suv-awd-6at-2r", f"{model}-2-5-s-select-suv-awd-6at-2r"]
        question = "Do you mean the base 2.5 S or the 2.5 S Select?"
        options = [
            {"label": label, "message": f"Show me the 2027 CX-5 {label}.", "trim_id": trim}
            for label, trim in zip(("2.5 S", "2.5 S Select"), trims)
        ]
        replies = iter([
            tool_response(), complete({"sections": [question]}),
            complete({"replacements": [], "choices": [{"section_index": 0, "options": options}]}),
            complete({"sections": ["Here is the selected CX-5.", "Vehicle details."]}),
        ])
        instructions = []

        async def generate(client, url, **kwargs):
            instructions.append(kwargs["json"]["instructions"])
            return httpx.Response(200, json=next(replies))

        with patch("backend.main.load_settings", return_value={
            "OPENAI_API_KEY": "fixture-only", "OPENAI_MODEL": "fixture-model",
        }), patch("httpx.AsyncClient.post", new=generate), TestClient(create_app()) as client:
            response = client.post("/chat", json={"message": "What about the basic one in the last card?"})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(validate_blocks(body), [])
            self.assertEqual(body["blocks"][0]["text"], question)
            group = body["blocks"][1]
            self.assertTrue(group["choice"])
            self.assertEqual([action["vehicle_action"]["trim_id"] for action in group["actions"]], trims)
            action = group["actions"][0]
            chosen = client.post("/chat", json={
                "message": action["message"], "vehicle_action": action["vehicle_action"],
            })
            self.assertEqual(chosen.status_code, 200)
            self.assertEqual(chosen.headers["Cache-Control"], "no-store")
            card = next(block for block in chosen.json()["blocks"] if block["type"] == "ui")
            self.assertEqual(card["component"], "VehicleDetails")
            self.assertEqual(card["props"]["records"][0]["selected_trim_id"], trims[0])
        self.assertIn("always present them as selectable UI", instructions[2])

    def test_repeated_greetings_and_catalog_queries_make_new_model_calls(self):
        import json
        import httpx
        from test_openai_runtime import complete

        requests = []
        async def generate(client, url, **kwargs):
            payload = kwargs["json"]
            requests.append(payload)
            self.assertFalse(payload["store"])
            sections = [f"Fresh response {len(requests)}"]
            if payload["input"] != "hello":
                facts = json.loads(payload["input"])["grounded_sections"]
                self.assertEqual(len(facts), 2)
                sections.extend(facts[1:])
            return httpx.Response(200, json=complete({"sections": sections}))

        with patch("backend.main.load_settings", return_value={
            "OPENAI_API_KEY": "fixture-only", "OPENAI_MODEL": "fixture-model",
        }), patch("httpx.AsyncClient.post", new=generate), TestClient(create_app()) as client:
            for index, prompt in enumerate(["hello", "hello", "Show Mazda SUVs.", "Show Mazda SUVs."], 1):
                response = client.post("/chat", json={"message": prompt})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers["Cache-Control"], "no-store")
                blocks = response.json()["blocks"]
                self.assertEqual(blocks[0]["text"], f"Fresh response {index}")
                if index > 2:
                    self.assertTrue(any(block.get("component") == "CarList" for block in blocks))
        self.assertEqual(len(requests), 4)
        self.assertEqual(len({request["instructions"].splitlines()[0] for request in requests}), 4)

    def test_missing_key_returns_error_instead_of_scripted_answer(self):
        with patch("backend.main.load_settings", return_value={}), TestClient(create_app()) as client:
            response = client.post("/chat", json={"message": "hello"})
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_vehicle_clicks_use_fresh_generation_and_exact_catalog_selection(self):
        import json
        import httpx
        from test_openai_runtime import complete

        requests = []

        async def generate(client, url, **kwargs):
            requests.append(json.loads(kwargs["json"]["input"]))
            return httpx.Response(200, json=complete({"sections": ["Fresh answer.", "Vehicle information."]}))

        model = "us-2027-cx90-phev"
        trim = f"{model}-phev-preferred-suv-awd-8at-3r"
        action = {"intent": "colors", "model_id": model, "trim_id": trim}
        with patch("backend.main.load_settings", return_value={
            "OPENAI_API_KEY": "fixture-only", "OPENAI_MODEL": "fixture-model",
        }), patch("httpx.AsyncClient.post", new=generate), TestClient(create_app()) as client:
            prompt = "I want to choose a color for the 2027 CX-90 Plug-in Hybrid."
            for _ in range(2):
                response = client.post("/chat", json={"message": prompt, "vehicle_action": action})
                self.assertEqual(response.status_code, 200)
                card = next(block for block in response.json()["blocks"] if block["type"] == "ui")
                self.assertEqual(card["component"], "ColorOptions")
                record = card["props"]["records"][0]
                self.assertEqual([item["trim_id"] for item in record["trims"]], [trim])
                names = {color["name"] for color in record["colors"]}
                self.assertIn("Deep Crystal Blue Mica", names)
                self.assertNotIn("Melting Copper Metallic", names)
            color = next(item for item in record["colors"] if item["name"] == "Deep Crystal Blue Mica")
            selected = client.post("/chat", json={
                "message": "Show me Deep Crystal Blue Mica.",
                "vehicle_action": {**action, "intent": "color_preview", "color_id": color["color_id"]},
            })
            self.assertEqual(selected.status_code, 200)
            card = next(block for block in selected.json()["blocks"] if block["type"] == "ui")
            self.assertEqual(card["component"], "VehicleDetails")
            details = card["props"]["records"][0]
            self.assertEqual(details["selected_color_id"], color["color_id"])
            self.assertEqual([item["trim_id"] for item in details["trims"]], [trim])
            self.assertTrue(details["specifications"])
            self.assertTrue(any(asset["color_code"] == color["color_code"] for asset in details["assets"]))
            self.assertFalse(any(block.get("component") == "ColorOptions" for block in selected.json()["blocks"]))
            invalid = client.post("/chat", json={
                "message": prompt, "vehicle_action": {**action, "color_id": "invalid"},
            })
            self.assertEqual(invalid.status_code, 422)
        self.assertEqual([item["question"] for item in requests], [prompt, prompt, "Show me Deep Crystal Blue Mica."])

    def test_ambiguous_cx90_color_question_exposes_both_choices_and_continues(self):
        import json
        import httpx
        from test_openai_runtime import complete

        prompts = []

        async def generate(client, url, **kwargs):
            payload = json.loads(kwargs["json"]["input"])
            prompts.append(payload["question"])
            draft = payload["grounded_sections"]
            sections = ["Which CX-90 version would you like?"] if len(draft) == 1 else draft
            return httpx.Response(200, json=complete({"sections": sections}))

        with patch("backend.main.load_settings", return_value={
            "OPENAI_API_KEY": "fixture-only", "OPENAI_MODEL": "fixture-model",
        }), patch("httpx.AsyncClient.post", new=generate), TestClient(create_app()) as client:
            response = client.post("/chat", json={"message": "Show me CX-90 colors."})
            self.assertEqual(response.status_code, 200)
            group = next(block for block in response.json()["blocks"] if block["type"] == "actions")
            self.assertEqual([action["label"] for action in group["actions"]],
                             ["Inline 6 Turbo (mild hybrid)", "Plug-in Hybrid"])
            for action, model in zip(group["actions"], ["us-2027-cx90-mhev", "us-2027-cx90-phev"]):
                followup = client.post("/chat", json={"message": action["message"]})
                self.assertEqual(followup.status_code, 200)
                card = next(block for block in followup.json()["blocks"] if block["type"] == "ui")
                self.assertEqual(card["component"], "ColorOptions")
                self.assertEqual(card["props"]["records"][0]["model_id"], model)
                self.assertFalse(any(block["type"] == "actions" for block in followup.json()["blocks"]))
        self.assertEqual(prompts, [
            "Show me CX-90 colors.", "Show me CX-90 mild hybrid colors.", "Show me CX-90 plug-in hybrid colors.",
        ])

    def test_confirmed_comparison_uses_exact_trims_and_fresh_model_calls(self):
        import json
        import httpx
        from test_openai_runtime import complete

        trim_ids = [
            "us-2027-cx90-mhev-3-3-turbo-preferred-suv-awd-8at-3r",
            "us-2027-cx90-phev-phev-preferred-suv-awd-8at-3r",
        ]
        payload = {
            "message": "Compare the CX-90 Turbo Preferred with the CX-90 PHEV Preferred.",
            "vehicle_action": {"intent": "comparison", "trim_ids": trim_ids},
        }
        calls = []

        async def generate(client, url, **kwargs):
            request = json.loads(kwargs["json"]["input"])
            calls.append(request)
            self.assertEqual([item["trim"] for item in request["catalog"]["configurations"]],
                             ["3.3 Turbo Preferred", "PHEV Preferred"])
            return httpx.Response(200, json=complete({"sections": [f"Fresh comparison {len(calls)}", "Pair."]}))

        with patch("backend.main.load_settings", return_value={
            "OPENAI_API_KEY": "fixture-only", "OPENAI_MODEL": "fixture-model",
        }), patch("httpx.AsyncClient.post", new=generate), TestClient(create_app()) as client:
            for count in (1, 2):
                response = client.post("/chat", json=payload)
                self.assertEqual(response.status_code, 200)
                blocks = response.json()["blocks"]
                self.assertEqual(blocks[0]["text"], f"Fresh comparison {count}")
                card = next(block for block in blocks if block.get("component") == "CarComparison")
                self.assertEqual([item["trim_id"] for item in card["props"]["records"]], trim_ids)
            for invalid in (trim_ids[:1], [trim_ids[0]] * 2, [trim_ids[0], "unknown"]):
                payload["vehicle_action"]["trim_ids"] = invalid
                self.assertEqual(client.post("/chat", json=payload).status_code, 422)
        self.assertEqual(len(calls), 2)
