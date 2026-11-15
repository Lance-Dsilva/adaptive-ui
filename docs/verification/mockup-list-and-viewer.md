# Mockup list and interactive vehicle viewer — 2026-11-14

Local repository: `/Users/lancedsilva/Documents/ChatGPT/Adaptive UI/adaptive-ui`.

## Visual references

Inspected the local model-discovery and inline-3D mockups. Discovery uses compact stacked photo/name/price/chevron rows. The vehicle viewer uses an inline stage, drag, rotate buttons, zoom, and reset. Screenshot example values are not catalog data.

## Implementation

- `frontend/src/CarList.jsx` and `styles.css`: compact full-row native buttons, independent bounded vertical list scroll, overflow-aware hint, filter scroll reset, preserved expandable information and comparison flow. The list can chain scrolling into the conversation at its boundaries.
- `frontend/src/VehicleVisualization.jsx` and `.css`: verified ordered-image rotation, pointer dragging, zoom controls, pinch handling, reset, keyboard arrow/Home controls, frame preload and image-error recovery. Native vertical touch scrolling is permitted. Configuration and color selectors only contain verified sequences.
- `frontend/src/VehicleExperience.jsx`: visible **3D / 360°** detail action and inline viewer. Unsupported selections retain an explicit unavailable state with still photos.
- `data/mazda/us/2027/visualizations.csv` and `frontend/assets/vehicle-rotations/`: sourced manifests and locally cached frames. Asset origins, ordering, hashes and applicability are recorded in the research audit. No mesh or interior panorama is fabricated.

## Local browser evidence

At 390 px, the SUV list overflowed inside its own region; keyboard PageDown reached the last result. Applying Hybrids reset list scrollTop to zero and removed the scroll hint when the two results fit. Full-row navigation opened the correct details.

The CX-5 2.5 S Rhodium White sequence rendered actual locally served 1024×1024 images. Rotate right moved frame 1 to 2; horizontal drag reached frame 13 with a visibly different angle. Zoom increased to 125%; reset returned frame 1 and 100%. ArrowLeft at frame 1 wrapped to frame 48. The detail-page action opened the same applicable viewer.

At 320 px, document clientWidth and scrollWidth were both 320 and the rotation image loaded. Physical mobile pinch and VoiceOver have not been exercised; accessible zoom buttons were verified.

Evidence: `scrollable-model-list-390.jpg`, `cx5-360-drag-390.jpg`. Screenshots show the states tested, not a claim of full vehicle/media coverage.

## Validation and coverage

80 backend tests and 56 frontend tests passed; production build passed. Backend acceptance checks locally cached WebP bytes and distinguishes verified frame records from unresolved data and absent meshes.

Final coverage: 10 sequences / 480 frames / 9,604,528 bytes, one Rhodium White exterior sequence per supported product trim. All five CX-5 product trims and five CX-90 MHEV product trims are enabled. CX-90 Preferred has an incomplete manifest; Mazda3/PHEV, other colors, interior panoramas, and mesh-based free-orbit views remain unavailable.

After expansion, browser verification loaded the CX-90 Select sequence, switched to S Premium Plus, confirmed the corresponding local frame path and 1024-pixel decoded image, wrapped to frame 48, then rotated to frame 7. At 320 px the expanded viewer still had no document overflow; the Reset control stayed unbroken. Screenshot: `cx90-360-final-390.jpg`. See `docs/research/3d-asset-audit.md` for source proof and remaining gaps. No deployment or cloud execution performed.
