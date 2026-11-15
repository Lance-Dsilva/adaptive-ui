"""Grounded catalog conversation shared by offline and accelerated AI requests."""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Sequence
from zoneinfo import ZoneInfo

from .orchestration import CallTool

logger = logging.getLogger(__name__)
MODEL_PATTERN = r"\b(?:cx[ -]?(?:5|30|50|70|90)|mazda\s?3|mx[ -]?5)\b"


@dataclass
class Selection:
    year: int = 2027
    models: list[str] = field(default_factory=list)
    body_style: str | None = None
    drivetrain: str | None = None
    budget: float | None = None
    powertrain: str | None = None
    model_powertrains: dict[str, str] = field(default_factory=dict)
    mode: str = "discovery"


def _text(value: str) -> str:
    return value.casefold().replace("’", "'").replace("‑", "-").replace("–", "-")


def _powertrain(text: str) -> str | None:
    if re.search(r"(?:don't|doesn't|do not|does not|no|without|never).{0,35}(?:plug|charg)", text):
        return "mild_hybrid"
    if re.search(r"plug[ -]?in|plugged in|\bphev\b", text):
        return "plug_in_hybrid"
    if re.search(r"mild hybrid|\bmhev\b", text):
        return "mild_hybrid"
    if "hybrid" in text:
        return "hybrid"
    return None


def _apply(text: str, selection: Selection) -> None:
    year = re.search(r"\b(20\d{2})\b", text)
    if year:
        selection.year = int(year[1])
    models = list(re.finditer(MODEL_PATTERN, text))
    if models:
        selection.models = list(dict.fromkeys(re.sub(r"[ -]", "", match[0]) for match in models))
        selection.model_powertrains = {}
    body = re.search(r"\b(suv|sedan|hatchback)s?\b", text)
    if body:
        selection.body_style = body[1]
    drive = re.search(r"\b(awd|fwd|rwd)\b", text)
    if drive:
        selection.drivetrain = drive[1].upper()
    budget = re.search(r"(?:under|below|up to|less than|budget(?: of)?|maximum|max)\s*\$?\s*(\d[\d,]*(?:\.\d+)?)\s*(k\b)?", text)
    if budget:
        selection.budget = float(budget[1].replace(",", "")) * (1000 if budget[2] else 1)
    requested_powertrain = _powertrain(text)
    if requested_powertrain:
        selection.powertrain = requested_powertrain
    if len(models) > 1:
        # Qualifiers after a named model apply to that model, not every comparison entry.
        selection.powertrain = None
        for index, match in enumerate(models):
            end = models[index + 1].start() if index + 1 < len(models) else len(text)
            qualifier = _powertrain(text[match.end():end])
            if qualifier:
                selection.model_powertrains[re.sub(r"[ -]", "", match[0])] = qualifier
    if re.search(r"all (?:mazda )?(?:models|cars|vehicles)|reset|clear filters", text):
        selection.models = []
        selection.body_style = None
        selection.drivetrain = None
        selection.budget = None
        selection.powertrain = None
        selection.model_powertrains = {}


def selection_for(message: str, history: Sequence[str] = ()) -> Selection:
    """Use prior filter state for referential and model-specific follow-up requests."""
    mode_patterns = (
        ("comparison", r"compare|comparison|versus|\bvs\b"),
        ("financing", r"financ|monthly|payment|apr|credit|eligible|lease|offers?|down[ -]?payment"),
        ("visualization", r"3d|360|rotat"),
        ("colors", r"colou?r|paint|soul red"),
        ("gallery", r"photos?|pictures?|images?|gallery"),
        ("details", r"details|tell me|specifications|trims|price breakdown|destination|msrp"),
    )
    selection = Selection()
    # Replay each turn using the same reset rule as a fresh request. Historical
    # standalone searches must not leak old model/budget filters into follow-ups.
    for turn in [*history[-20:], message]:
        text = _text(turn)
        if re.fullmatch(r"\s*(?:hi|hello|hey|good morning|good afternoon|good evening|thanks|thank you)[!.,\s]*", text):
            continue
        mode = next((name for name, pattern in mode_patterns if re.search(pattern, text)), "discovery")
        if (mode == "details" and re.search(r"under|below|up to|less than|budget|maximum|\bmax\b", text)
                and not re.search(r"details|tell me|specifications|trims|price breakdown|destination", text)):
            mode = "discovery"
        followup = re.search(
            r"\b(those|these|ones|them|it|that|same|also|instead)\b|^and\b|^under\b|^what about\b"
            r"|^which is a good (car|vehicle|suv)[?.!]*$",
            text,
        )
        if not (followup or mode != "discovery" and not re.search(MODEL_PATTERN, text)):
            selection = Selection()
        _apply(text, selection)
        selection.mode = mode
    return selection


def filter_records(records: list[dict], selection: Selection) -> list[dict]:
    """Select source records without changing their nested data or metadata."""
    result = []
    for record in records:
        family = record["model_family"]
        if selection.models and family not in selection.models:
            continue
        powertrain = selection.model_powertrains.get(family, selection.powertrain)
        if powertrain is not None and record["powertrain"] != powertrain:
            if powertrain != "hybrid" or record["powertrain"] not in {"mild_hybrid", "plug_in_hybrid"}:
                continue
        result.append(record)
    return result


def _recovery(text: str) -> str | None:
    if re.search(r"book|appointment|test[ -]?drive|schedule", text):
        return (
            "Open Chat options, then Request test drive, to save a local request with your "
            "preferred model, date, time, and contact details. It is saved on this computer "
            "only and is not sent to a dealership. No availability is checked and no "
            "appointment is confirmed. Contact the dealership separately to arrange your visit."
        )
    if re.search(r"in stock|inventory|dealer quote|out.the.door|buy now", text):
        return (
            "Live dealer stock and transaction quotes require a dealership connection. "
            "I can show published U.S. starting MSRP and trims for the researched 2027 models."
        )
    return None


def _money(value: str | float | Decimal) -> str:
    return f"${Decimal(str(value)):,.2f}"


def _warnings(result: dict) -> list[str]:
    records = result.get("records", [])
    if any("offer_type" in record for record in records):
        return ["Published offers retain their eligibility and location restrictions. Dealer confirmation and credit approval are required."]
    if not records:
        return ["The researched snapshot has limited coverage. Confirm availability and current terms with the dealer."]
    caveats = []
    if any("colors" in record for record in records):
        caveats.append("Exact exterior and interior combinations require dealer confirmation.")
    if any("assets" in record for record in records):
        caveats.append("Photos may show a different model year or configuration.")
    return [" ".join(caveats)] if caveats else []


def _trim_lines(record: dict) -> list[str]:
    lines = []
    for trim in record["trims"]:
        amount = _money(trim["msrp_usd"]) if trim["msrp_usd"] else "unavailable"
        line = f"{trim['name']} · {trim['drivetrain']} — MSRP {amount}"
        if trim["msrp_usd"] and trim["destination_usd"]:
            subtotal = Decimal(trim["msrp_usd"]) + Decimal(trim["destination_usd"])
            line += f"; destination {_money(trim['destination_usd'])}; subtotal {_money(subtotal)} before options, taxes, and other fees"
        lines.append(line)
    return lines


def _single_model(records: list[dict]) -> str | None:
    if len(records) == 1:
        return None
    if {record["powertrain"] for record in records if record["model_family"] == "cx90"} >= {
        "mild_hybrid", "plug_in_hybrid"
    } and all(record["model_family"] == "cx90" for record in records):
        return "Which CX-90 version would you like?"
    names = ", ".join(record["name"] for record in records)
    return f"Which model do you mean? The matching choices are {names}. Specify the powertrain when choosing CX-90."


async def _vehicle_response(text: str, selection: Selection, record: dict, call_tool: CallTool) -> list[str]:
    model_id = record["model_id"]
    model_name = record["name"]
    arguments = {"model_id": model_id}
    trim_label = re.search(r"premium plus|turbo premium|preferred|premium|select|sport", text)
    if trim_label:
        matches = [
            trim for trim in record["trims"]
            if re.search(r"\b" + trim_label[0] + r"\b", _text(trim["name"]))
            and ("plus" in trim_label[0] or "plus" not in _text(trim["name"]))
        ]
        if len(matches) > 1:
            configurations = [
                f"{trim['name']} ({trim['body_style']}, {trim['drivetrain']}, "
                f"{trim['seating_capacity'].replace('|', ' or ')} seats)"
                for trim in matches
            ]
            return [f"Which {model_name} configuration do you mean? " + " or ".join(configurations) + "?"]
        if not matches:
            return ["Please specify the exact trim and seating configuration so I can use the correct price and equipment."]
        arguments["trim_id"] = matches[0]["trim_id"]
    if selection.mode == "financing":
        arguments = {"model_id": model_id, "as_of": datetime.now(ZoneInfo("America/Chicago")).date().isoformat()}
        if "lease" in text:
            arguments["offer_type"] = "lease"
        result = await call_tool("get_financing_offers", arguments, "offers-1")
        lines = []
        for offer in result["records"]:
            if offer["offer_type"] == "apr":
                value = f"{offer['apr_percent']}% APR for up to {offer['term_months_max']} months"
            elif offer["offer_type"] == "loyalty_cash":
                value = f"{_money(offer['cash_amount_usd'])} loyalty cash" if offer["cash_amount_usd"] else "Loyalty terms unavailable"
            else:
                value = "Published lease terms" if offer["lease_monthly_usd"] else "Lease terms unavailable"
            lines.append(
                f"{value}. Recorded expiry {offer['expires_on'] or 'unspecified'}; "
                f"status as of {offer['as_of']}: {offer['expiry_status']}. {offer['eligibility']}"
            )
        return [
            f"Here are the published financing observations for {model_name}.",
            "\n".join(lines) or "Verified terms for this offer are unavailable in the researched snapshot.",
            *_warnings(result),
        ]

    if selection.mode == "details":
        result = await call_tool("get_car_details", arguments, "detail-1")
        details = result["records"][0]
        return [
            f"Here are the published configurations and price breakdowns for {model_name}.",
            "\n".join(_trim_lines(details)),
            *_warnings(result),
        ]

    result = await call_tool("get_vehicle_media", arguments, "media-1")
    media = result["records"][0]
    if selection.mode == "colors":
        colors = media["colors"]
        if "soul red" in text:
            colors = [color for color in colors if "soul red" in _text(color["name"])]
            codes = {color["color_code"] for color in colors if color["color_code"]}
            if len(codes) == 1:
                result = await call_tool(
                    "get_vehicle_media", {**arguments, "color_code": next(iter(codes))}, "media-2"
                )
                colors = result["records"][0]["colors"]
            if not colors:
                return [f"The researched {model_name} records do not verify Soul Red availability. Open its color options to review the published choices."]
        lines = list(dict.fromkeys(
            f"{color['name']} ({color['location']}) — "
            + (f"paint/material charge {_money(color['extra_cost_usd'])}" if color["extra_cost_usd"] else "surcharge not stated")
            for color in colors
        ))
        return [
            f"Here are the published color and material choices for {model_name}.",
            "\n".join(lines) or "No verified color records are available for this selection.",
            *_warnings(result),
        ]
    if selection.mode == "visualization":
        return [
            f"Here is the visualization information for {model_name}.",
            "No verified interactive rotation or 3D model is available for this selection. "
            "Browse its published configuration photos instead.",
            *_warnings(result),
        ]
    images = [asset for asset in media["assets"] if asset["asset_kind"] == "image"]
    return [
        f"Here are the sourced photos for {model_name}.",
        f"Reference images for {model_name} are shown with their configuration labels."
        if images else "No applicable photos were found in the researched snapshot.",
        *_warnings(result),
    ]


async def _compare_response(records: list[dict], call_tool: CallTool) -> list[str]:
    if any(sum(other["model_family"] == record["model_family"] for other in records) > 1 for record in records):
        return ["For CX-90, should I compare the Inline 6 Turbo mild hybrid or the Plug-in Hybrid? Name the version so the comparison uses the right configuration."]
    if len(records) < 2:
        return ["Which two models would you like to compare? Include CX-90’s mild-hybrid or plug-in version if you choose it."]
    trims = [
        min((trim for trim in record["trims"] if trim["msrp_usd"]), key=lambda trim: Decimal(trim["msrp_usd"]))
        for record in records
    ]
    result = await call_tool("compare_cars", {"trim_ids": [trim["trim_id"] for trim in trims]}, "comparison-1")
    lines = [
        f"{record['model']['name']} {record['name']} · {record['drivetrain']} — MSRP {_money(record['msrp_usd'])}"
        for record in result["records"]
    ]
    return [
        "Here is a comparison of the lowest-MSRP matching configuration for each requested model.",
        "\n".join(lines),
        *_warnings(result),
    ]


async def curate(message: str, call_tool: CallTool, history: Sequence[str] = ()) -> list[str]:
    """Produce ordered sections grounded in the local domain tools."""
    text = _text(message).strip()
    recovery = _recovery(text)
    if recovery:
        return [recovery]
    selection = selection_for(message, history)
    if selection.year != 2027:
        return [f"This catalog covers researched 2027 U.S. Mazda models. It has no researched coverage for {selection.year}. Try “Show me 2027 Mazda models.”"]
    relevant = re.search(
        r"mazda|cx[ -]?\d|mx[ -]?5|suv|sedan|hatchback|cars?|vehicles?|models?|hybrid|phev|mhev|compare|budget|under|below|trims?|details|those|these|ones|them",
        text,
    )
    if not relevant and selection.mode == "discovery":
        return ["I can help explore researched 2027 Mazda models, trims, prices, colors, photos, and financing observations. Try “Show me Mazda SUVs under $35,000.”"]
    if re.search(r"\b(it|that one|this one)\b", text) and len(selection.models) != 1:
        return ["Which model do you mean? Name the Mazda model so I can use the right catalog records."]
    arguments = {"model_year": selection.year}
    for name, value in (("body_style", selection.body_style), ("drivetrain", selection.drivetrain), ("max_msrp_usd", selection.budget)):
        if value is not None:
            arguments[name] = value
    try:
        result = await call_tool("search_cars", arguments, "discovery-1")
        records = filter_records(result["records"], selection)
        represented = {record["model_family"] for record in records}
        missing = set(selection.models) - represented
        if missing:
            return [
                f"No matching researched 2027 configuration was found for {', '.join(sorted(missing))}. "
                "This snapshot covers Mazda3, CX-5, and CX-90. Model coverage, body style, powertrain, and price filters can limit the results. "
                "Try another covered model or clear the filters."
            ]
        if not records:
            return ["No researched 2027 configurations match those choices. Try a higher starting-MSRP limit or “Show all Mazda models.” The catalog has limited model coverage."]
        if selection.mode == "comparison":
            return await _compare_response(records, call_tool)
        if selection.mode != "discovery":
            clarification = _single_model(records)
            if clarification:
                return [clarification]
            return await _vehicle_response(text, selection, records[0], call_tool)
    except Exception:
        logger.error("Catalog conversation lookup failed")
        return ["I couldn’t read the requested vehicle information. Please try your request again."]
    lines = [
        (record["name"] if record["name"].casefold().startswith(record["brand"].casefold())
         else f"{record['brand']} {record['name']}") + " — "
        + (f"from {_money(record['matching_msrp_usd'])}" if record["matching_msrp_usd"] is not None else "starting MSRP unavailable")
        + f" ({record['powertrain'].replace('_', ' ')})"
        for record in records
    ]
    return ["Here are the matching researched 2027 Mazda models.", "\n".join(lines)]
