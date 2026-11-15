# Vehicle rotation / 3D asset audit — 2026-11-14

**Resolved:** ten genuine 48-frame exterior rotations are now verified and cached locally: all five CX-5 product trims and five CX-90 MHEV product trims, each in Rhodium White Premium. The initial blocked investigation below is retained as evidence; explicit user approval subsequently permitted public Mazda downloads.

## New findings from the actual local source bundle

The saved official CX-5 and CX-90 product pages use two separate layers: Mazda's `vehicleVisualizer` / `VehicleExperienceViewer` controllers and a shared viewer library. The locally saved `/tmp/adaptive-mazda-research/viewer.js` is the shared library. It exposes **CI360** for image-sequence rotation and **Pannellum** for interior panoramas. It is not a vehicle mesh loader. No GLB/GLTF URL occurs in that library or the saved CX-5/CX-90/build HTML.

CI360 supports an explicit `imageListX` or a filename template plus `amountX` and `indexZeroBase`. Its generic default `image-{index}.jpg` is library boilerplate, not a Mazda vehicle naming contract. Using that default to guess URLs would be unsupported.

The saved 2027 CX-5 product configuration identifies 32 trim/color exterior folders; CX-90 identifies 49. For example, CX-5 2.5 S / Rhodium White 51K points to `/content/dam/musa/vehicle-assets/siteassets/vehicles/2027/cx-5/04-btv/001-trims/34-jellies/2-5-s/exterior/51k`. This is an actual source value, but it supplies neither filenames nor sequence order. The page's initial viewer props have empty `exteriorDirectory`, `exteriorPrefix`, `exteriorExtension`, `totalImages`, and `images: []`. Only `initialIndex: 1` is populated. The controllers must populate the actual sequence after trim/color selection.

A distinct potential path is the exact `vehicle360TrimImage` in interior color metadata. CX-5 2.5 S Black Cloth (`C_KJN`) identifies `/content/dam/musa/vehicle-assets/siteassets/vehicles/2027/cx-5/04-btv/001-trims/34-jellies/2-5-s/interior/my26-cx-5-interior-s-cloth-black.jpg`. This is more specific than an exterior directory, but the local downloaded bundle does not contain that image or controller mapping proving its panorama projection. It must be downloaded/decoded and checked before enabling a panorama; its older filename must also remain disclosed.

## Exact next source inputs

These script URLs are present verbatim in the saved official CX-5 HTML (base `https://www.mazdausa.com`):

- `/etc.clientlibs/musa/components/vehicleVisualizer/v1/vehicleVisualizer/clientlib.lc-cc1ff5de16e6ba3afb1eadc84c1f870b-lc.min.js`
- `/etc.clientlibs/mazda-experience/clientlibs/clientlib-viewer360.lc-379a558827ff12f2e50a09c4355b85b7-lc.min.js`
- `/etc.clientlibs/mazda-experience/components/vehicleExperienceViewer/v1/vehicleExperienceViewer/clientlib.lc-e488d285df9d82cfac65516a50b9b11a-lc.min.js`

The first and third controllers are not present among the existing local research downloads. Their code is the next precise input needed: it should reveal the folder-to-ordered-images resolver or request endpoint. After obtaining that published response, verify every returned frame URL is a real image; inspect angular progression and wraparound; retain the model, trim, color, source URL and any filename-year discrepancy. A sequence is a photo-based exterior spin, not a free-orbit 3D mesh.

## Current verification and blocked operation

Inspected saved product HTML, parsed trim JSON, viewer props, build HTML and the downloaded viewer library. No verified ordered exterior sequence or mesh can yet be assembled from those files. Repository visualization metadata remains 81 unresolved directories plus 3 empty mesh findings. No frontend or dataset changes were made by this audit.

An attempted local `curl` download of the three exact script URLs was rejected by automatic approval review. Its stated reason was that external downloads conflict with the local-only/no-remote-execution instruction; the rejection specifically required inspecting already-downloaded files and prohibited indirect workarounds. The operation was not retried through another network tool. Fresh public-controller retrieval therefore needs explicit user approval to resolve that rejection, despite earlier approved local media downloads. The engineering manager has the exact URLs and can request approval for this bounded read-only source retrieval.


## Approved retrieval and verified sequence

The user explicitly approved public Mazda asset downloads to the Mac. The exact two controllers listed above were then retrieved successfully. `vehicleVisualizer` requests `<data-cmp-page-path>/_jcr_content.trimdata.json?exteriorDirectory=<encoded folder>`. This endpoint was derived from actual publisher code and page metadata, not guessed filenames. Its response contains 48 ordered image names/asset IDs, `indexZero=1`, `indexLength=3`, `extension=webp`, and `dynamicMediaEnabled=true`.

The publisher viewer builds Dynamic Media URLs from those returned IDs/names with `preferwebp=true&quality=82&width=1024`. All 48 were downloaded locally; every response was a valid WebP, every file decoded to 1024×1024 pixels using macOS `sips`, and all 48 SHA256 hashes are distinct. Total compressed image bytes: **854,722**. Frames 001, 009, 017, 025, 033, 041 and 048 were visually inspected: they progress from one side around the front, opposite side and rear to the near-start angle. This is a full exterior image sequence, not a CSS rotation of a still photo and not a polygon mesh.

`visualizations.csv` promotes only **27CX525S-51K** to `status=verified_frames` and `kind=exterior_image_sequence`. Model: `us-2027-cx5`; trim code: `27CX525S`; color: `51K`. The 48 original downloaded files are cached unchanged in `frontend/assets/vehicle-rotations/cx5-27cx525s-51k/`, with ordered local URLs in `frame_urls_json`. The frontend build must copy this assets subtree; the registered viewer must allow its bounded local URL prefix.

Source evidence is retained in `docs/research/cx5-rotation-evidence/`: `cx5-manifest.json`, `manifest-url.txt`, `script-urls.txt`, `frames.json` (original remote URLs), and `frame-checks.json` (byte counts and SHA256 per frame). Downloaded controller scripts remain in `/tmp/adaptive-3d-audit/`.

Applicability follows the publisher's 2027 product-page configuration. The source filenames include `My26`; this is preserved and does not independently prove an earlier vehicle model year. The CSV caption reads “CX-5 2.5 S — Rhodium White Premium. Representative exterior preview; configuration details may differ.” Exact depicted equipment remains subject to confirmation. Other trim/color combinations are not silently substituted or marked verified. No downloadable GLB/GLTF mesh has been verified. Public-source access does not establish redistribution permission; existing permission status stays unverified.


## Bounded coverage expansion

The same verified resolver was queried for one recorded Rhodium White (`51K`) folder per remaining product trim. Nine additional manifests returned complete ordered image lists and were verified, cached and promoted. Total: **10 sequences / 480 frames / 9,604,528 compressed bytes**. Every new frame returned valid WebP bytes and decoded to 1024×1024; every sequence has 48 distinct hashes. A contact sheet of frames 001/013/025/037/048 for each new sequence was visually inspected and confirms side/front/opposite-side/rear/wraparound progression.

Supported product codes (all color `51K`):

- CX-5: `27CX525S`, `27CX5SE`, `27CX5PF`, `27CX5PR`, `27CX5PP`.
- CX-90 MHEV: `27C90SE`, `27C90PR`, `27C90PP`, `27C90SPR`, `27C90SPP`.

The CX-90 Sport product codes are shared by two-row/three-row catalog configurations; these are explicitly representative exterior previews and do not establish depicted seating. Other colors have not been promoted. PHEV/Mazda3 remain without a verified rotation sequence.

**CX-90 Preferred (`27C90PF`) remains unresolved:** its actual response reports `size=48`, `indexZero=0`, `indexLength=0`, `dynamicMediaEnabled=true`, but `images=[]` and a long frame-like filename prefix. Unlike the other nine responses, it does not enumerate usable asset IDs/names. No frames were guessed or substituted. The anomalous response is retained in local research storage `/tmp/adaptive-3d-audit/expansion/27C90PF.json`.

Expansion provenance, remote URLs, hashes and the visual contact sheet are retained in `docs/research/cx5-rotation-evidence/expansion/`. Viewer images remain in `frontend/assets/vehicle-rotations/`; no further source downloads are necessary for this bounded expansion.
