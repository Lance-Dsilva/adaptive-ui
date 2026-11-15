# Clean vehicle research and comparison UI

Research and implementation brief, 2026-11-14. User's latest screenshot and request supersede the earlier comparison layout while retaining Aurora's violet accent and subtle lavender/blue palette.

## Research findings applied

- [NN/g: visual design principles](https://www.nngroup.com/articles/principles-visual-design/) supports a deliberate hierarchy, consistent scale, grouping and contrast. The old comparison repeated the selected pair in a large panel, a list and a table; the redesign prioritizes the actual comparison.
- [NN/g: progressive disclosure](https://www.nngroup.com/articles/progressive-disclosure/) supports immediate access to important facts and expandable access to detailed information. Rich specifications remain available without presenting every field at once.
- [GOV.UK summary lists](https://design-system.service.gov.uk/components/summary-list/) provides a semantic label/value structure for a single vehicle. Side-by-side data stays in a semantic comparison table rather than misusing a summary list for multiple vehicles.

## Implementation targets

1. Compact selection state while picking. After the second choice, show the comparison and collapse candidate selection behind Change vehicles.
2. One clear year/model identity, one selected configuration, one applicable photo area, and exact selected-configuration pricing per vehicle. Avoid combining a base price with equipment from a higher trim.
3. Key facts first: powertrain, drivetrain, seats, rows, price and available efficiency/cargo figures. All applicable detailed source records remain reachable in labeled groups.
4. Large image areas, restrained white cards, fine dividers and one accent color. Avoid oversized selection panels, tiny thumbnails and a greyed-out wall of unselected vehicles.
5. Source captions and applicability remain visible. A prior-year image is a clearly labelled reference, never a silently substituted current-year or different-powertrain image.
6. Preserve source dates, units, fuel-grade qualifiers, missing-field states, and manufacturer links. Do not invent a value to fill a comparison cell.
7. At 320/390 px, controls wrap and the composer remains accessible. Comparison selection, configuration switching, photo navigation and all disclosures must work by keyboard/native controls.

## Data baseline

The repository already contains 1,034 specification records: Mazda3 147, CX-5 365, CX-90 MHEV 492, and CX-90 PHEV 30. This pass exposes those source-backed records in richer discovery/detail/comparison props, rather than only three comparison rows. Official image research is recorded separately with provenance and explicit reference applicability.

## Enrichment

Added 105 verified PHEV specification rows (35 fields for each of three trims), bringing the catalog to 1,139 specification records. Added four verified official image URLs: a 2027 Mazda3 release photograph and three explicitly labelled 2026 PHEV reference images. See [source and media audit](vehicle-media-2026-11-14.md). The catalog covers four model variants and 27 configurations; counts describe source records, not unique consumer features or independently verified photographs throughout the existing catalog.

## Verification

- Backend: 80 unittest tests passed locally after adding regressions for “full details” and “complete details” routing. Routine catalog detail requests retain local deterministic presentation; unknown substantive questions still use the model.
- Frontend: 51 component tests passed and production build passed. Final detail groups and compact source links were visually inspected.
- Browser at 390 px: two selections collapse the chooser, focus the comparison heading, load actual Mazda3/CX-5 photographs, and expose the configuration selectors.
- Browser at 320 px: document width and scroll width both 320; changing Mazda3 to Select Sport updates base MSRP from $24,750 to $25,740. Replacing Mazda3 with PHEV preserves CX-5 and displays the explicit 2026 reference image.
- “Show full details for CX-90 PHEV” opens the full details view locally; its disclosure exposes the added charging, dimensions, cargo, towing, and efficiency records with original qualifiers and source links.
- The UI team reviewed `docs/verification/clean-comparison-390.jpg`: no material visual blockers at 390 px. This is visual review, not physical-device or screen-reader certification.
- React review: component state stays local, updates preserve other selection/configuration state, native labelled selects and disclosures remain keyboard-operable, comparison uses semantic column/row headers, and no new UI dependencies were introduced.

## Implementation files

Frontend: `CarList.jsx`, `VehicleExperience.jsx`, `styles.css`, and component tests. Backend: `catalog.py`, `presentation.py`, `conversation.py`, `openai_runtime.py`, rich-prop/runtime/catalog assertions, and UI registry properties. Data: `assets.csv`, `specifications.csv`, `sources.csv`, `coverage.csv`. Research and verification artifacts live under `docs/`.

## Remaining limits

Exact 2027 PHEV photographs and complete Mazda3 trim/body-style imagery remain unavailable; generic and prior-year photos are labelled. No verified 3D model or rotation sequence was added. The failed free-form detail request seen before the local-routing fix does not establish reliability of arbitrary live model questions; this pass verifies the updated catalog experience and is not a blanket GA certification. No deployment performed.
