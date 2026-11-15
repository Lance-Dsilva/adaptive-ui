# Mazda U.S. 2027 research

Research snapshot checked on November 13, 2026. The scope is U.S. national information. Monetary values are USD. Official Mazda releases, specification decks, and public product configuration data supply the records. `sources.csv` lists the references and dates.

The snapshot covers announced 2027 Mazda3 sedan/hatchback, CX-5, CX-90 mild hybrid, and CX-90 plug-in hybrid configurations. `coverage.csv` records findings for the rest of Mazda's U.S. lineup and unresolved research areas. This is a bounded snapshot of published information. Exact dealer inventory and transaction prices require a location and current dealer data.

## Files and joins

| File | Contents and keys |
| --- | --- |
| `models.csv` | Four model/powertrain records across three model families. `model_id` is the primary key. |
| `trims.csv` | 27 body/drivetrain/seating configurations. Join to models by `model_id`. `trim_id` is unique. |
| `specifications.csv` | Published specifications and features. Exact configuration rows use `trim_id`. Product-page rows use `product_trim_code` and state their applicability. |
| `colors.csv` | Exterior colors and interior materials. Product configuration rows use `product_trim_code`. Model-level and family-level rows have broader applicability. |
| `assets.csv` | Image and document URLs, captions, color/trim associations, filename year hints, and verification status. Family media has `model_family` and an empty `model_id`. |
| `visualizations.csv` | 360-degree image-directory references and findings about 3D model availability. |
| `offers.csv` | Two national APR programs and four model-level records for the 2027 loyalty program, with expiry and eligibility. |
| `coverage.csv` | Model-year coverage, unavailable details, and source conflicts. |
| `sources.csv` | Official URLs, publication dates where known, and the research date. |

Every researched record includes `source_id`, `source_url`, and `checked_on`. CSVs use UTF-8 and standard quoted-field escaping. Empty fields mean unknown or unspecified. Zero is an explicit numeric value. Values containing multiple choices use `|` where documented by the column name or value. `source_record_json` and `frame_urls_json` contain JSON within a CSV cell.

## Prices and financing

MSRP excludes destination, taxes, title, options, and dealer fees. Destination charges have separate columns, including Alaska. Dealer pricing can differ. The CX-90 two-row and three-row prices come from the dated pricing release. Its product configuration objects share trim codes and contain seating adjustments, so a trim code alone cannot identify a final configuration or price.

The APR observations expire November 30, 2026. Their availability depends on credit approval, participating dealers, inventory, and the recorded conditions. `apr_percent` uses percentage points, so `2.9` means 2.9%. `payment_per_1000_usd` is the publisher's example per $1,000 financed. It is not a vehicle-specific payment quote. The loyalty program is recorded for all four model records and applies to both Mazda3 body styles.

The reviewed lease examples use 2026 vehicles. Verified 2027 lease terms and model-specific Mazda3/PHEV APR terms remain gaps. Tools should report those gaps and evaluate an offer's expiry against the request date.

## Images, colors, and visualization

Product image paths are resolved to absolute URLs for retrieval. The original color metadata is retained in `source_record_json`, including original paths, URL parameters, swatch values, and empty fields. Some assets published within a 2027 page have older-year filenames. `filename_year_hint` records the filename evidence. It does not independently establish the depicted vehicle's model year.

`product_trim_code` links color choices and image records. Exact exterior/interior combinations and seating restrictions still need the configurator's combination rules. A blank color surcharge means the source omitted a numeric price. The release's unusual Mazda3 color name “Premium Quartz Metallic” is retained as published and requires confirmation before normalization.

Twenty-three representative image URLs returned HTTP 200 during local HEAD requests. Those rows carry `http_200_head_sample`. Other links carry `url_observed`. This verifies sampled URL availability. Image content, browser cross-origin behavior, and every individual asset still require implementation-time checks. Source color fields occasionally differ, such as a named swatch's `hexValue` and `majorColorHex`. Both are retained for review.

The CX-5 and CX-90 pages expose exterior image directories and interior viewer images. A directory reference requires a resolved frame manifest and validated ordering before an image-spin control can use it. The current `frame_urls_json` values are empty arrays. The reviewed sources did not provide a verified downloadable 3D mesh. `model_3d_url` therefore remains empty.

The UI can use the catalog for vehicle cards, image galleries, and color swatches. Interactive rotation needs verified image frames or a supported 3D model. Full 3D material switching additionally needs mappings from Mazda's color codes to the model's materials. Asset reuse permission and embedding support have not been verified.

## Scope and refresh

The Mazda3 and CX-90 PHEV product pages still expose 2026 configuration codes. Their 2027 records use the dated U.S. announcements and specification deck. Mazda's U.S. release says two-row CX-90 variants replace the CX-70. The current official press-kit index still lists CX-30, CX-50, and MX-5 as 2026. `coverage.csv` expresses the limits of this research without treating a missing announcement as proof of cancellation.

Refresh the dated announcements and product configuration sources, reconcile model years and trim identities, then refresh expiring offers. Update `checked_on` only for records actually rechecked. Preserve source labels and record conflicts when sources differ. A model-year query should return confirmed matching records together with relevant coverage gaps.
