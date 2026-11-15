"""Map retained discovery results into the local React catalog component."""

from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from jsonschema import Draft202012Validator

from .orchestration import ToolResult


def _photos(record: dict, trim: dict | None = None) -> list[dict]:
    from .catalog import _asset_applies
    photos = []
    for asset in record["assets"]:
        if asset["asset_kind"] != "image" or not _asset_applies(asset, record, [trim] if trim else record["trims"]):
            continue
        parsed = urlsplit(asset["url"])
        if parsed.scheme != "https" or not parsed.hostname:
            continue
        reference = bool(asset.get("reference_model_id"))
        if reference:
            label = f"{asset['source_model_year']} reference image; {record['model_year']} model may differ"
        elif asset["product_trim_code"]:
            label = f"{asset['source_model_year']} model / trim-group reference image"
        else:
            label = f"{asset['source_model_year']} model reference image; trim unspecified"
        photos.append({**deepcopy(asset), "applicability_label": label})
    return sorted(photos, key=lambda asset: bool(asset.get("reference_model_id")))


def _image_props(record: dict) -> dict:
    candidates = _photos(record)
    if not candidates:
        return {"image_url": None, "image_caption": "", "image_is_reference": False}
    starting_codes = {trim["product_trim_code"] for trim in record["trims"]
                      if trim["msrp_usd"] and float(trim["msrp_usd"]) == record["matching_msrp_usd"]}
    asset = min(candidates, key=lambda asset: (
        bool(asset.get("reference_model_id")),
        not bool(asset["product_trim_code"]),
        asset["product_trim_code"] not in starting_codes,
        asset["source_field"] != "trim_image",
        asset["fetch_status"] != "http_200_head_sample",
    ))
    return {"image_url": asset["url"],
            "image_caption": asset["applicability_label"] + (". " + asset["caption"] if asset["caption"] else ""),
            "image_is_reference": bool(asset.get("reference_model_id"))}


def _representative_image(record: dict) -> str | None:
    return _image_props(record)["image_url"]


def _configurations(record: dict) -> list[dict]:
    configurations = []
    for trim in record["trims"]:
        specifications = [spec for spec in record.get("specifications", [])
                          if (not spec["trim_id"] or spec["trim_id"] == trim["trim_id"])
                          and (not spec["product_trim_code"] or spec["product_trim_code"] == trim["product_trim_code"])]
        configurations.append({
            **deepcopy(trim),
            "specifications": deepcopy(specifications),
            **_image_props({**record, "trims": [trim],
                "matching_msrp_usd": float(trim["msrp_usd"]) if trim["msrp_usd"] else None}),
            "photos": _photos(record, trim),
        })
    return configurations


def _car_props(record: dict) -> dict:
    return {
        "id": record["model_id"],
        "name": record["name"] if record["name"].casefold().startswith(record["brand"].casefold()) else f"{record['brand']} {record['name']}",
        "year": int(record["model_year"]),
        "msrp": record["matching_msrp_usd"],
        **_image_props(record),
        "powertrain": record["powertrain"],
        "configurations": _configurations(record),
        "photos": _photos(record),
        "specifications": deepcopy(record.get("specifications", [])),
        "source_url": record.get("source_url", ""),
        "checked_on": record.get("checked_on", ""),
        "trims": [
            {
                "id": trim["trim_id"],
                "name": trim["name"],
                "msrp": float(trim["msrp_usd"]) if trim["msrp_usd"] else None,
                "drivetrain": trim["drivetrain"],
            }
            for trim in record["trims"]
        ],
    }


class DiscoveryPresentation:
    def __init__(self, project_root: Path) -> None:
        path = project_root / "registries" / "ui_tools.yaml"
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        if manifest["schema_version"] != 1 or manifest["registry"] != "ui_tools":
            raise ValueError("Unsupported UI tool manifest.")

        self._source = project_root / "frontend" / "src" / "CarList.jsx"
        self._result = self._validator(manifest["result_schema"])
        self._tool = next(
            (tool for tool in manifest["tools"] if tool["name"] == "render_car_list"),
            None,
        )
        self._input = None
        if manifest["enabled"] is True and self._tool and self._tool.get("enabled") is True:
            if self._tool["implementation"] != "frontend/src/CarList.jsx":
                raise ValueError("Unsupported render_car_list implementation.")
            self._input = self._validator(self._tool["input_schema"])

    @staticmethod
    def _validator(schema: dict) -> Draft202012Validator:
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)

    async def select(self, sections: tuple[str, ...], calls: tuple[ToolResult, ...], record_filter=None) -> dict:
        if self._input is None or len(sections) not in (2, 3) or not self._source.is_file():
            return {}
        discovery = next(
            (call for call in calls if call.call_id == "discovery-1" and call.name == "search_cars"),
            None,
        )
        if discovery is None or not discovery.result["records"]:
            return {}

        records = discovery.result["records"]
        if record_filter is not None:
            records = record_filter(records)
        cars = [_car_props(record) for record in records]
        self._input.validate({"cars": cars, "fallback_text": sections[1]})
        result = {
            "component": self._tool["component"],
            "code": self._source.read_text(encoding="utf-8"),
            "props": {"cars": cars},
            "fallback_text": sections[1],
        }
        self._result.validate(result)
        return {1: result}
