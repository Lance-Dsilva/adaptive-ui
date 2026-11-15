"""Bind local domain functions using the checked-in tool manifest."""

from collections.abc import Callable, Mapping
from pathlib import Path
from functools import partial
from typing import Any

from jsonschema import Draft202012Validator
import yaml

from .catalog import Catalog
from .appointments import get_test_drive_options


class ToolRegistry:
    def __init__(self, project_root: Path) -> None:
        path = project_root / "registries" / "agent_tools.yaml"
        manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
        if manifest["schema_version"] != 1 or manifest["registry"] != "agent_tools":
            raise ValueError("Unsupported domain tool manifest.")

        self._result = self._validator(manifest["result_schema"])
        self._tools: dict[str, tuple[Draft202012Validator, Callable[..., dict]]] = {}
        catalog = Catalog(project_root / manifest["data_root"])
        bindings = {
            f"backend.catalog:Catalog.{name}": getattr(catalog, name)
            for name in ("search_cars", "get_car_details", "compare_cars",
                         "get_financing_offers", "get_vehicle_media")
        }
        bindings["backend.appointments:get_test_drive_options"] = partial(get_test_drive_options, project_root)
        if manifest["enabled"]:
            for entry in manifest["tools"]:
                if entry.get("enabled") is not True:
                    continue
                name = entry["name"]
                if name in self._tools:
                    raise ValueError(f"Duplicate enabled tool: {name}")
                self._tools[name] = (
                    self._validator(entry["input_schema"]),
                    bindings[entry["implementation"]],
                )

    @staticmethod
    def _validator(schema: dict) -> Draft202012Validator:
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(
            schema, format_checker=Draft202012Validator.FORMAT_CHECKER
        )

    def invoke(self, name: str, arguments: Mapping[str, Any]) -> dict:
        if name not in self._tools:
            raise ValueError(f"Domain tool is unavailable: {name}")
        validator, implementation = self._tools[name]
        parameters = dict(arguments)
        validator.validate(parameters)
        # JSON Schema considers an integral JSON number such as 2027.0 an integer.
        if "model_year" in parameters:
            parameters["model_year"] = int(parameters["model_year"])
        result = implementation(**parameters)
        self._result.validate(result)
        return result
