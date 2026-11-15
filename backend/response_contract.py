"""Application-owned semantic response blocks, independent of model typography."""
import re
from decimal import Decimal
from copy import deepcopy

from .conversation import filter_records, selection_for

_GREETING = r'(?:hi|hello|hey|good morning|good afternoon|good evening)'
_NAMES = {'cx5': 'CX-5', 'cx90': 'CX-90', 'mazda3': 'Mazda3', 'cx30': 'CX-30', 'cx50': 'CX-50', 'cx70': 'CX-70', 'mx5': 'MX-5'}
_POWER = {'plug_in_hybrid': 'Plug-in hybrid', 'mild_hybrid': 'Mild hybrid', 'hybrid': 'Hybrid'}
_ATTRIBUTION = re.compile(
    r'\b(?:sources?|citations?)\b|\bchecked\s+(?:on\s+)?(?:\d{4}-\d{2}-\d{2}|[A-Za-z]+\s+\d{1,2})\b|https?://',
    re.I,
)
_INLINE_ATTRIBUTION = re.compile(r'\s*\((?:sources?|citations?|(?:last )?checked)\b[^()]*\)', re.I)


def _customer_text(text):
    """Remove stray attribution from generated copy while preserving adjacent facts."""
    lines = []
    for line in text.splitlines():
        line = _INLINE_ATTRIBUTION.sub('', line)
        if not _ATTRIBUTION.search(line):
            lines.append(line)
            continue
        sentences = re.split(r'(?<=[.!?])\s+', line)
        facts = [sentence for sentence in sentences if not _ATTRIBUTION.search(sentence)]
        if facts:
            lines.append(' '.join(facts))
    return '\n'.join(lines).strip()


def shopping_message(message):
    return re.sub(r'^\s*' + _GREETING + r'\b[!,.:\s—-]*', '', message, flags=re.I).strip() or message


def greeting_response(message):
    if not re.fullmatch(r'\s*' + _GREETING + r'[!.,\s]*', message, re.I):
        return None
    return {'blocks': [
        {'id': 'greeting-answer', 'type': 'text', 'role': 'answer', 'text': 'Hi! What are you looking for in your next Mazda?'},
        {'id': 'greeting-body', 'type': 'text', 'role': 'body', 'text': 'Explore published 2027 U.S. models, trims, and starting prices.'},
        {'id': 'greeting-actions', 'type': 'actions', 'actions': [
            {'id': 'explore-suvs', 'label': 'Explore SUVs', 'message': 'Show me Mazda SUVs.'},
            {'id': 'compare-models', 'label': 'Compare models', 'message': 'Show all 2027 Mazda models.', 'compare': True},
        ]},
        {'id': 'greeting-catalog', 'type': 'disclosure', 'title': 'About this catalog',
         'text': 'Covers researched 2027 U.S. Mazda3, CX-5, and CX-90 models. Check with the dealership for current inventory.'},
    ]}


def context_items(selection):
    items = [str(selection.year)]
    items.extend(_NAMES.get(model, model) for model in selection.models)
    if selection.body_style:
        items.append({'suv': 'SUVs', 'sedan': 'Sedans', 'hatchback': 'Hatchbacks'}[selection.body_style])
    if selection.drivetrain:
        items.append(selection.drivetrain)
    if selection.budget is not None:
        amount = Decimal(str(selection.budget))
        places = max(2, -amount.as_tuple().exponent) if amount != amount.to_integral_value() else 0
        items.append(f'Up to ${amount:,.{places}f} MSRP')
    if selection.powertrain:
        items.append(_POWER.get(selection.powertrain, selection.powertrain))
    for family, power in selection.model_powertrains.items():
        items.append(f'{_NAMES.get(family, family)} · {_POWER.get(power, power)}')
    return items


def without_budget(selection):
    # Self-contained query binds this operation to its original result, even if
    # the shopper has made another request since that result was displayed.
    models = ' and '.join(
        _NAMES.get(model, model) + (' ' + _POWER[selection.model_powertrains[model]] if model in selection.model_powertrains else '')
        for model in selection.models
    )
    parts = ['Show me', str(selection.year), 'Mazda', models]
    parts += [selection.drivetrain or '', _POWER.get(selection.powertrain, '').lower(),
              {'suv': 'SUVs', 'sedan': 'sedans', 'hatchback': 'hatchbacks'}.get(selection.body_style, 'models')]
    return ' '.join(part for part in parts if part) + '.'


def cx90_choice_actions(message, selection, candidates):
    if (selection.mode == "discovery" or "cx90" not in selection.models
            or selection.model_powertrains.get("cx90") or selection.powertrain):
        return None
    if selection.mode == "comparison" and len(selection.models) < 2:
        return None
    matches = list(re.finditer(r"\bcx[ -‐‑–]?90\b", message, re.I))
    if len(matches) != 1:
        return None
    powers = {
        record["powertrain"] for record in filter_records(candidates, selection)
        if record["model_family"] == "cx90"
    }
    if not {"mild_hybrid", "plug_in_hybrid"} <= powers:
        return None
    end = matches[0].end()
    return {
        "id": "cx90-powertrain-choices", "type": "actions", "label": "Choose a CX-90 powertrain",
        "actions": [
            {"id": "cx90-mild-hybrid", "label": "Inline 6 Turbo (mild hybrid)",
             "message": message[:end] + " mild hybrid" + message[end:]},
            {"id": "cx90-plug-in-hybrid", "label": "Plug-in Hybrid",
             "message": message[:end] + " plug-in hybrid" + message[end:]},
        ],
    }


def decorate_response(response, message, history, *, candidates=()):
    blocks = deepcopy(response['blocks'])
    selection = selection_for(message, history)
    has_cards = any(block['type'] == 'ui' for block in blocks)
    empty = len(blocks) == 1 and blocks[0].get('text', '').startswith(('No researched', 'No matching researched'))
    result = []
    for index, block in enumerate(blocks):
        block['id'] = f'block-{index}'
        if block['type'] == 'text':
            text = _customer_text(block['text'])
            if not text:
                continue
            block['text'] = text
            if empty:
                block['role'] = 'status'
            elif text.startswith(('Starting MSRP excludes', 'Published offers retain', 'Images retain', 'Published terms are subject')):
                block['role'] = 'notice'
            else:
                block['role'] = 'answer' if not result else 'body'
        else:
            block['role'] = 'card'
            if block['type'] == 'ui':
                block['fallback_text'] = _customer_text(block['fallback_text']) or 'Vehicle information could not be displayed.'
        if (block['type'] == 'ui' and not any(b['type'] == 'context' for b in result)) or empty:
            result.append({'id': 'effective-context', 'type': 'context', 'items': context_items(selection)})
        result.append(block)
    if (has_cards or empty) and selection.budget is not None and selection.mode == 'discovery':
        result.append({'id': 'result-actions', 'type': 'actions', 'actions': [
            {'id': 'clear-budget', 'label': 'Clear budget', 'message': without_budget(selection)},
        ]})
    choices = cx90_choice_actions(message, selection, candidates) if not has_cards else None
    if choices:
        result.append(choices)
    if history and not has_cards and not choices and any(
        block['type'] == 'text' and re.search(
            r'^\s*(?:\[question\]\s+)?What matters most to you(?:\?|:)', block['text'], re.I | re.M
        )
        for block in blocks
    ):
        prior = selection_for(history[-1], history[:-1])
        if prior.body_style == 'suv':
            result.append({'id': 'shopping-priorities', 'type': 'actions', 'actions': [
                {'id': 'lower-price', 'label': 'Lower price',
                 'message': 'Which of those Mazda SUVs has the lowest starting price?'},
                {'id': 'more-seats', 'label': 'More seats',
                 'message': 'Which of those Mazda SUVs offers more seats?'},
            ]})
    return {'blocks': result or [{'id': 'answer', 'type': 'text', 'role': 'answer',
                                  'text': 'What would you like to know about the vehicle?'}]}
