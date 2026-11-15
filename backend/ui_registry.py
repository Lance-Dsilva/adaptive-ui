"""Build UI results from retained tool records and checked-in React components."""

from copy import deepcopy
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from .orchestration import ToolResult
from .presentation import _car_props


_BINDINGS = {
    "render_car_list": ("CarList", "frontend/src/CarList.jsx", {"search_cars"}),
    "render_car_details": (
        "VehicleDetails", "frontend/src/VehicleExperience.jsx", {"get_car_details"},
    ),
    "render_car_comparison": (
        "CarComparison", "frontend/src/VehicleExperience.jsx", {"compare_cars"},
    ),
    "render_financing_offers": (
        "FinancingOffers", "frontend/src/VehicleExperience.jsx", {"get_financing_offers"},
    ),
    "render_vehicle_gallery": (
        "VehicleGallery", "frontend/src/VehicleExperience.jsx",
        {"get_vehicle_media", "get_car_details"},
    ),
    "render_color_options": (
        "ColorOptions", "frontend/src/VehicleExperience.jsx",
        {"get_vehicle_media", "get_car_details"},
    ),
    "render_vehicle_visualization": (
        "VehicleVisualization", "frontend/src/VehicleExperience.jsx",
        {"get_vehicle_media", "get_car_details"},
    ),
}


class UIRegistry:
    def __init__(self, root: Path):
        self.root = root
        manifest = yaml.safe_load(
            (root / "registries/ui_tools.yaml").read_text(encoding="utf-8")
        )
        if manifest["schema_version"] != 1 or manifest["registry"] != "ui_tools":
            raise ValueError("Unsupported UI registry manifest")
        self._tools = {}
        self._result_validator = self._validator(manifest["result_schema"])
        if manifest["enabled"] is True:
            for tool in manifest["tools"]:
                if tool.get("enabled") is not True:
                    continue
                component, implementation, _ = _BINDINGS[tool["name"]]
                if tool["component"] != component or tool["implementation"] != implementation:
                    raise ValueError(f"Unrecognized UI binding: {tool['name']}")
                if tool["name"] in self._tools:
                    raise ValueError(f"Duplicate UI binding: {tool['name']}")
                self._tools[tool["name"]] = (tool, self._validator(tool["input_schema"]))

    @staticmethod
    def _validator(schema: dict) -> Draft202012Validator:
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)

    def render(
        self, tool_name: str, source_call: ToolResult,
        record_indices: list[int], fallback_text: str,
    ) -> dict:
        if tool_name not in self._tools:
            raise ValueError(f"UI tool unavailable: {tool_name}")
        tool, validator = self._tools[tool_name]
        component, implementation, compatible = _BINDINGS[tool_name]
        if source_call.name not in compatible:
            raise ValueError(f"{tool_name} cannot render source tool {source_call.name}")
        records = source_call.result.get("records")
        if not isinstance(records, list):
            raise ValueError("The source tool result must contain records")
        if not isinstance(record_indices, list) or any(
            type(index) is not int or not 0 <= index < len(records)
            for index in record_indices
        ):
            raise ValueError("Record indices must be nonnegative integers within the source result")
        if len(record_indices) != len(set(record_indices)):
            raise ValueError("Record indices must be unique")
        selected = deepcopy([records[index] for index in record_indices])
        if tool_name == "render_car_list":
            props = {"cars": [_car_props(record) for record in selected]}
        else:
            props = {"records": selected}
        validator.validate({**props, "fallback_text": fallback_text})
        result = {
            "component": component,
            "code": (self.root / implementation).read_text(encoding="utf-8"),
            "props": props,
            "fallback_text": fallback_text,
        }
        self._result_validator.validate(result)
        return result
