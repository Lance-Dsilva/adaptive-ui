# Official vehicle media refresh — 2026-11-14

All extraction, downloads, image inspection and CSV edits ran on the local Mac. Four newly imported URLs returned HTTP 200 to full GET requests and decoded as vehicle images. No URLs were constructed by changing model years or filenames. Local evidence is in `/tmp/adaptive-media-refresh/`: source HTML, parsed PHEV `data-props`, response headers, downloaded images and `verified-media.json`. SHA256 values are retained in each asset row.

## Added records

| Asset | Source identification | Catalog use |
| --- | --- | --- |
| `media-20261114-mazda3-release` | Image embedded in [official 2027 Mazda3 release/press kit](https://news.mazdausa.com/2027-Mazda3) | Model-level illustrative image; exact trim/equipment unspecified |
| `media-20261114-26c9ppf` | Official [CX-90 PHEV product page](https://www.mazdausa.com/vehicles/cx-90-phev), vehicleCode `26C9PPF`, PHEV Preferred | Clearly labeled 2026 reference only |
| `media-20261114-26c9ppr` | Same product page, vehicleCode `26C9PPR`, PHEV Premium Sport | Clearly labeled 2026 reference only |
| `media-20261114-26c9ppp` | Same product page, vehicleCode `26C9PPP`, PHEV Premium Plus | Clearly labeled 2026 reference only |

The source product JSON still explicitly identifies 2026 PHEV configurations. The PHEV photos are not substituted MHEV imagery. All three captions say: “2026 CX-90 Plug-in Hybrid reference image; 2027 appearance/equipment may differ.” Their source trim codes and source year remain unchanged.

The Mazda3 release photo was visually inspected and shows a vehicle, not a swatch or logo. Its 2027 applicability comes from the dated release, not filename inference. The imported caption deliberately makes no trim or equipment claim. The existing press-kit gallery reuses older-year filenames and does not establish exact 2027 configuration imagery. An inspected CX-90 newsroom gallery detail likewise supplied a photo URL and publication date but no explicit depicted-model-year/trim caption, so it was not promoted to an exact 2027 image.

## Data contract

`assets.csv` adds `applicability` and `reference_model_id`. Existing records retain their original fields and have blank new fields. New prior-year references use `applicability=model_reference`, blank `model_id`, the true `source_model_year=2026`, and `reference_model_id=us-2027-cx90-phev`. The backend must explicitly join that reference ID and the frontend must preserve the visible reference caption. These records do not establish exact trim compatibility. The Mazda3 release row has `applicability=model`, `model_id=us-2027-mazda3`, and source year 2027.

Totals after enrichment: **722 assets** (717 images, 5 documents), **17 sources**, **13 coverage rows**. Four new assets, two new sources, two new coverage findings. Existing records and their checked dates were not rewritten as newly verified.

## Remaining limits

Exact 2027 CX-90 PHEV images and complete exact Mazda3 sedan/hatchback/trim coverage remain unverified. No verified rotation frame manifest or 3D mesh was found. Existing media reuse/embedding permission remains unverified; this refresh does not grant publication rights. Third-party image delivery can fail, so the app must preserve its image-error fallback. Downloads stay in temporary local research storage; this change imports provenance-preserving remote URLs, not a production image cache.

## PHEV specification enrichment and verification

Added **105 rows: 35 fields for each of three PHEV trims**, bringing `specifications.csv` to **1,139 rows**. Existing rows are preserved. The [official 2027 CX-90 specification deck](https://news.mazdausa.com/download/27MY+CX-90+Spec+Deck+FINAL.pdf), pages **12–13**, supplies dimensions, cargo measurements, estimated efficiency/range, charging and towing information. A fresh local download matches the previously downloaded PDF byte-for-byte (619,809 bytes; SHA256 `1332e7d91977c50a014fcb8dcdfeb84e4a851fc28f170ed2ba4ccdcb00ed110f`). Both pages were rendered and visually inspected to verify merged columns and units. Five catalog tests passed after the append.

Qualifiers remain in field names, values and applicability: 56 combined MPGe is electric plus gasoline; 26 combined MPG is gasoline; charging times retain state-of-charge interval, 75 F temperature, voltage and amperage. Cargo volumes 15.9/40.8/75.2 cubic feet explicitly require the two-seat third-row configuration shown in the PHEV column. PHEV towing is 3,500 lb; the 5,000-lb towing-package entry is in the High PT column and was not assigned to PHEV.

Source differences are retained instead of silently reconciled. The specification deck records 323 system horsepower on 93-octane fuel, while the existing release-derived field says 91 octane; its recommended-fuel row separately says 91 octane or above. The deck distinguishes AER 0–26 miles from RCDA 27 miles, while the release gives an up-to-27-mile electric range. New field names identify specification-deck values; previous release-derived values remain intact.

## MHEV five-passenger seating check

Five seats is a genuine published configuration, not a data error. The same official PDF, page **10**, lists option `2RW` as a two-row, five-passenger configuration in the **3.3 Turbo Premium Sport** and **3.3 Turbo S Premium Sport** columns only. Product summaries on pages 2–3 also identify the available 2R/5-passenger configuration. The [2027 pricing release](https://news.mazdausa.com/2026-10-27-2027-Mazda-CX-90-Pricing-and-Packaging) lists those two-row variants at $46,880 and $53,540 respectively, matching `trims.csv`. Thus model-level seating of 5, 7 or 8 represents alternative configurations; no individual vehicle seats all three capacities. This investigation changed no trim data.
