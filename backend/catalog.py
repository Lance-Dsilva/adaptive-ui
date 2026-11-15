"""Search the locally researched Mazda catalog."""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path


def _model_key(value: str) -> str:
    return "".join(character for character in value.casefold() if character.isalnum())


def _asset_applies(asset: dict, model: dict, trims: list[dict]) -> bool:
    if asset.get("reference_model_id"):
        reference_trim_id = asset.get("reference_trim_id")
        return (asset["reference_model_id"] == model["model_id"]
                and asset.get("applicability") == "model_reference"
                and not asset.get("model_id")
                and (not reference_trim_id or any(trim["trim_id"] == reference_trim_id for trim in trims)))
    return (asset["model_id"] == model["model_id"]
            and asset["source_model_year"] == model["model_year"]
            and (not asset["product_trim_code"] or asset["product_trim_code"] in
                 {trim["product_trim_code"] for trim in trims}))


class Catalog:
    def __init__(self, data_root: Path):
        self.data_root = data_root

    def _read(self, table: str) -> list[dict[str, str]]:
        with (self.data_root / f"{table}.csv").open(encoding="utf-8", newline="") as stream:
            return list(csv.DictReader(stream))

    def search_cars(
        self,
        model_year: int,
        model: str | None = None,
        body_style: str | None = None,
        drivetrain: str | None = None,
        max_msrp_usd: float | None = None,
    ) -> dict:
        """Return announced models with at least one matching configuration."""
        year = str(model_year)
        model_key = _model_key(model) if model is not None else None
        price_limit = Decimal(str(max_msrp_usd)) if max_msrp_usd is not None else None
        trims = self._read("trims")
        assets = self._read("assets")
        specifications = self._read("specifications")
        sources = self._read("sources")
        coverage = [
            row for row in self._read("coverage") if row["requested_model_year"] == year
        ]
        source_ids = {row["source_id"] for row in coverage}
        records = []

        for row in self._read("models"):
            if row["model_year"] != year or row["announcement_status"] != "officially_announced":
                continue
            model_id = row["model_id"]
            family = row["model_family"]
            if model_key is not None and model_key not in {
                _model_key(model_id),
                _model_key(family),
                _model_key(row["name"]),
                _model_key(f"{row['brand']} {row['name']}"),
                _model_key(f"{row['brand']} {family}"),
            }:
                continue

            matching_trims = [
                trim for trim in trims
                if trim["model_id"] == model_id
                and (body_style is None or trim["body_style"] == body_style)
                and (drivetrain is None or trim["drivetrain"] == drivetrain)
                and (
                    price_limit is None
                    or trim["msrp_usd"] and Decimal(trim["msrp_usd"]) <= price_limit
                )
            ]
            if not matching_trims:
                continue

            trim_codes = {trim["product_trim_code"] for trim in matching_trims}
            matching_assets = [asset for asset in assets if _asset_applies(asset, row, matching_trims)]
            trim_ids = {trim["trim_id"] for trim in matching_trims}
            matching_specs = [
                spec for spec in specifications
                if spec["model_id"] == model_id
                and (not spec["trim_id"] or spec["trim_id"] in trim_ids)
                and (not spec["product_trim_code"] or spec["product_trim_code"] in trim_codes)
            ]
            prices = [Decimal(trim["msrp_usd"]) for trim in matching_trims if trim["msrp_usd"]]
            records.append({
                **row,
                "trims": matching_trims,
                "assets": matching_assets,
                "specifications": matching_specs,
                "matching_msrp_usd": float(min(prices)) if prices else None,
            })
            source_ids.update(item["source_id"] for item in [row, *matching_trims, *matching_assets, *matching_specs])

        warnings = ["The catalog covers announced U.S. models. Dealer inventory was not checked."]
        if not coverage:
            warnings.append(f"The local snapshot has no coverage records for model year {year}.")
        warnings.extend(
            f"{row['subject']}: {row['notes']}"
            for row in coverage
            if row["status"] != "confirmed"
        )
        return {
            "records": records,
            "sources": [row for row in sources if row["source_id"] in source_ids],
            "checked_on": max(row["checked_on"] for row in sources),
            "warnings": warnings,
            "coverage": coverage,
        }

    def _selection(self, model_id: str, trim_id: str | None = None) -> tuple[dict, list[dict]]:
        model = next((row for row in self._read("models") if row["model_id"] == model_id), None)
        if model is None:
            raise ValueError(f"Unknown model_id: {model_id}")
        trims = [row for row in self._read("trims") if row["model_id"] == model_id]
        if trim_id is not None:
            trims = [row for row in trims if row["trim_id"] == trim_id]
            if not trims:
                raise ValueError(f"Trim {trim_id} does not belong to model {model_id}")
        return model, trims

    def _related(self, table: str, model: dict, trims: list[dict]) -> list[dict]:
        """Retain broader applicability labels while excluding conflicting identities."""
        trim_ids = {row["trim_id"] for row in trims}
        codes = {row["product_trim_code"] for row in trims if row["product_trim_code"]}
        result = []
        for row in self._read(table):
            if table == "assets":
                if _asset_applies(row, model, trims):
                    result.append(row)
                continue
            if row.get("model_id"):
                if row["model_id"] != model["model_id"]:
                    continue
            elif row.get("model_family") != model["model_family"]:
                continue
            if row.get("source_model_year") and row["source_model_year"] != model["model_year"]:
                continue
            if row.get("trim_id") and row["trim_id"] not in trim_ids:
                continue
            if row.get("product_trim_code") and row["product_trim_code"] not in codes:
                continue
            result.append(row)
        return result

    def _envelope(self, records: list[dict], source_rows: list[dict], warnings: list[str]) -> dict:
        source_ids = {row["source_id"] for row in source_rows}
        sources = [row for row in self._read("sources") if row["source_id"] in source_ids]
        dates = [row["checked_on"] for row in source_rows if row.get("checked_on")]
        return {
            "records": records,
            "sources": sources,
            "checked_on": min(dates),
            "warnings": warnings,
        }

    def get_car_details(self, model_id: str, trim_id: str | None = None) -> dict:
        model, trims = self._selection(model_id, trim_id)
        related = {
            table: self._related(table, model, trims)
            for table in ("specifications", "colors", "assets", "visualizations")
        }
        coverage = [
            row for row in self._read("coverage")
            if row["requested_model_year"] == model["model_year"]
        ]
        record = {**model, "trims": trims, **related, "coverage": coverage}
        rows = [model, *trims, *coverage]
        for entries in related.values():
            rows.extend(entries)
        warnings = [
            "MSRP excludes destination, taxes, title, options, and dealer fees.",
            "Product trim groups may cover multiple seating configurations. Preserve each record's applicability.",
            "Exact exterior/interior combinations require confirmation.",
        ]
        warnings.extend(f"{row['subject']}: {row['notes']}" for row in coverage)
        return self._envelope([record], rows, warnings)

    def compare_cars(self, trim_ids: list[str]) -> dict:
        if len(trim_ids) < 2 or len(set(trim_ids)) != len(trim_ids):
            raise ValueError("Comparison requires at least two distinct trim IDs")
        all_trims = {row["trim_id"]: row for row in self._read("trims")}
        records, rows, warnings = [], [], []
        for trim_id in trim_ids:
            if trim_id not in all_trims:
                raise ValueError(f"Unknown trim_id: {trim_id}")
            trim = all_trims[trim_id]
            details = self.get_car_details(trim["model_id"], trim_id)
            model = details["records"][0]
            records.append({
                **trim,
                "model": {key: value for key, value in model.items() if isinstance(value, str)},
                "specifications": model["specifications"],
                "colors": model["colors"],
                "assets": model["assets"],
            })
            rows.extend([trim, model, *model["specifications"], *model["colors"], *model["assets"]])
            warnings.extend(details["warnings"])
        return self._envelope(records, rows, list(dict.fromkeys(warnings)))

    def get_vehicle_media(
        self, model_id: str, trim_id: str | None = None, color_code: str | None = None
    ) -> dict:
        model, trims = self._selection(model_id, trim_id)
        related = {
            table: self._related(table, model, trims)
            for table in ("assets", "colors", "visualizations")
        }
        if color_code is not None:
            related = {
                table: [row for row in entries if row.get("color_code") == color_code]
                for table, entries in related.items()
            }
        record = {**model, "trims": trims, **related}
        rows = [model, *trims]
        for entries in related.values():
            rows.extend(entries)
        warnings = [
            "Family-level media retains broader applicability and may depict older filenames.",
            "Color combinations and seating restrictions require confirmation.",
            "Image-sequence directories are metadata. Verified frames or 3D meshes are required for rotation.",
        ]
        if color_code is not None and not any(related.values()):
            warnings.append(f"No verified media or color record for color code {color_code}.")
        return self._envelope([record], rows, warnings)

    def get_financing_offers(
        self, model_id: str, as_of: str, offer_type: str | None = None
    ) -> dict:
        requested_date = date.fromisoformat(as_of)
        model, _ = self._selection(model_id)
        offers = [
            row for row in self._read("offers")
            if row["model_id"] == model_id
            and row["model_year"] == model["model_year"]
            and (offer_type is None or row["offer_type"] == offer_type)
        ]
        records, warnings = [], []
        for row in offers:
            if row["starts_on"] and requested_date < date.fromisoformat(row["starts_on"]):
                status = "not_started"
            elif row["expires_on"] and requested_date > date.fromisoformat(row["expires_on"]):
                status = "expired"
            elif requested_date < date.fromisoformat(row["checked_on"]):
                status = "historical_availability_unknown"
            elif not row["expires_on"]:
                status = "expiry_unknown"
            else:
                status = "within_recorded_expiry"
            records.append({**row, "expiry_status": status, "as_of": as_of})
            if status != "within_recorded_expiry":
                warnings.append(f"{row['offer_id']}: {status}")
        if not offers:
            warnings.append("Verified terms for this requested offer are unavailable in the local snapshot.")
        warnings.append("Offers retain their recorded eligibility and geography. Availability and credit approval require dealer confirmation.")
        return self._envelope(records, [model, *offers], warnings)
