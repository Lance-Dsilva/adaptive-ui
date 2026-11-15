# Adaptive UI

Adaptive UI is a mobile-only chatbot interface. The latest Adaptive UI mockups are the design source of truth. The [design reference index](docs/design/mockups/README.md) links to the ten Aurora Light images in this repository.

## Architecture

The backend is a local FastAPI service that coordinates two agents. Domain functions read local CSV files and are exposed to Agent 1 through a Tool Registry. A separate UI function registry supplies React code for visual responses selected by Agent 2. Development commands, services, and tests run on the user's computer.

| Component | Responsibility |
| --- | --- |
| Mobile frontend | Accept chat messages and render ordered text and UI blocks according to the mockups. |
| FastAPI backend | Coordinate tool calls, preserve their results, run the two agents in sequence, and assemble the response. |
| Tool Registry | Expose domain functions such as `search_cars` and `compare_cars` with their input and output contracts. |
| CSV files | Supply the initial domain data, including image URLs where available. |
| Agent 1 | Call domain tools and curate an answer grounded in their results. |
| Agent 2 | Identify parts of the answer that can be supplemented with UI, select a UI function, map the source data to its inputs, and attach the returned React code. |
| UI function registry | Describe available UI functions, their input contracts, and the React code they return. |

## Data and tool definitions

Vehicle research lives in CSV files under [data/mazda/us/2027](data/mazda/us/2027/README.md). These contain U.S. Mazda model and trim data, prices, financing observations, specifications, colors, image references, visualization findings, and sources. The research snapshot is dated November 13, 2026. Coverage gaps and unverified 2027 details are recorded explicitly.

Tool discovery uses YAML manifests in [registries/agent_tools.yaml](registries/agent_tools.yaml) and [registries/ui_tools.yaml](registries/ui_tools.yaml). YAML supports readable descriptions, metadata, and nested JSON Schema input contracts. The backend will load and validate the manifests, bind their entries to implemented local functions, and give each agent the applicable tool definitions through the selected model runtime. Domain implementations will be Python functions and UI implementations will supply React code and props.

The domain manifest enables only `search_cars`. The UI manifest enables only `render_car_list`. Other tools remain disabled. Agent 1's tools read CSV data. Agent 2's tools map that data into UI inputs. Both use source dates, model-year applicability, and asset status when producing a response.

## Request flow

1. The user asks a question, such as “Can you show me what cars are available for 2027?”
2. FastAPI passes the question and relevant conversation context to Agent 1. Agent 1 selects a Tool Registry function and supplies its arguments.
3. The function reads the CSV data and returns raw structured results. FastAPI retains the complete result of every tool call.
4. Agent 1 curates the response. FastAPI hands Agent 2 both the curated response and the complete original tool results, with references connecting the answer to its source records.
5. Agent 2 identifies sections that benefit from UI, maps source records into the corresponding UI functions, and calls them to obtain React code or presents available choices as buttons.
6. FastAPI sends the lead answer and any other prose the selected UI does not fully cover, followed by the UI. Text represented by a card stays available as its fallback.

## Preserve tool data through the agent handoff

The complete raw tool response is part of the handoff contract. This includes image URLs, image lists, captions, identifiers, links, nested metadata, and other fields even when Agent 1 does not mention them in its prose.

FastAPI retains the original structured tool results and attaches them to the handoff. Agent 1's curated text is stored alongside those results. This makes preservation independent of an LLM reproducing every field correctly.

- Preserve field names, values, nesting, list order, and the association between each record and its images. Keep null and empty values intact.
- Carry image URLs verbatim, including query parameters. Associate each tool result with its tool name, call ID, and arguments so multiple results remain distinguishable.
- Give Agent 2 access to every retained result. It can map the fields required by a UI function into props while the complete source result remains available in the handoff.
- Retain the complete curated answer even if UI selection or rendering fails.

## Proposed message contract

Use an ordered `blocks` array for the curated text and optional UI. Each UI block carries the React code returned by a UI function and the structured props that code consumes. The car and URL below are placeholders.

```json
{
  "blocks": [
    {
      "type": "text",
      "text": "Here is a car matching your request."
    },
    {
      "type": "ui",
      "component": "CarList",
      "code": "function CarList({ cars }) { return <ul>{cars.map(car => <li key={car.id}><img src={car.image_url} alt={car.name} /><span>{car.name}</span></li>)}</ul>; }",
      "props": {
        "cars": [
          {
            "id": "sample-car-1",
            "name": "Example Car",
            "year": 2027,
            "image_url": "https://example.invalid/car.jpg?view=front"
          }
        ]
      },
      "fallback_text": "Example Car — model year 2027."
    }
  ]
}
```

Agent 2 presents the model facts as a card. The matching paragraph is kept in `fallback_text` and shown if the card fails to render. The image URL in the props is copied exactly from the retained source record.

The JSON envelope and field names above are a proposed contract. Streaming JSON lines can carry the same ordered blocks if streaming is chosen later.

## Run vehicle discovery locally

The mobile web app includes the welcome screen, in-chat discovery, published trim details, price and hybrid filters, and a model comparison using starting MSRP, powertrain, and drivetrain.

FastAPI serves the built app and the chat endpoint. The deterministic discovery adapter handles year-based discovery prompts and the SUV suggestion. The presentation adapter returns the checked-in React source and validated props. The browser renders the bundled `CarList` registered for that component name and uses the supplied text if rendering fails. Vehicle photo URLs come from the catalog and may require network access in the browser. The app shows a placeholder when an applicable image is missing or fails to load.

Build the web app from cached npm dependencies:

```sh
cd frontend
npm ci --offline --no-audit --no-fund
npm run build
cd ..
```

With Python 3.13 and a local wheel directory containing the requirements and their dependencies:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-index --find-links /path/to/wheels -r requirements-test.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000/ in a browser. To call the API directly, use a second terminal:

```sh
curl --fail-with-body http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"Can you show me what cars are available for 2027?"}'
```

## Implementation status

The app uses a local FastAPI service, CSV catalog tools, and registered React UI components. OpenAI configuration and expanded journeys are described below. Current mockup interaction verification is recorded in `docs/verification/mockup-list-and-viewer.md`; historical verification reports describe earlier snapshots.

## Verification targets

- A tool result with image URLs and nested metadata reaches Agent 2 with all fields and values intact, including when Agent 1's prose omits those fields.
- Multiple tool calls retain their individual results and record-to-image associations.
- UI props use the correct source records and preserve image URL values exactly.
- Converting a section to UI preserves surrounding text and block order.
- Empty results, tool failures, unsupported UI, and rendering failures produce usable chat responses.
- The mobile layout matches the latest mockups and verifies locally.

See [AGENTS.md](AGENTS.md) for the engineering workflow. The local discovery service uses the researched CSVs and the domain tool manifest.

## OpenAI and expanded vehicle journeys

Copy `.env.example` to `.env` and enter `OPENAI_API_KEY` locally. The server reads configuration for every request. `OPENAI_MODEL` defaults to `gpt-6-luna`. Each submitted chat message makes a new OpenAI Responses API request with `store: false`, including repeated messages. Catalog lookups run locally and matched facts ground the generated cards. The assistant uses hosted web search for current Mazda information and public research outside the catalog, with clickable links beside web-backed answers. Chat responses use `Cache-Control: no-store`. If the API key is missing or generation fails, chat reports the error. The offline catalog adapter is available to tests.

The app includes sourced vehicle details, specifications, price breakdowns, color options, image galleries, financing observations and an estimate calculator. Verified exterior rotation frames are cached locally and rendered with drag, zoom, reset, and keyboard controls for supported configurations. See `docs/research/3d-asset-audit.md` for current coverage. Unsupported configurations retain a clearly labelled photo fallback; no verified 3D mesh is available.

The chat menu opens a test-drive demo. After review, the app validates the vehicle and preferred time, clears the form, and confirms that the demo completed. The demo does not collect contact information, save submissions, or book appointments.

See `docs/verification/mockup-list-and-viewer.md` for current local tests and interaction checks. A passing local catalog check is not public GA approval. Remaining areas include unsupported media/configurations, physical-device and assistive-technology coverage, arbitrary live-model reliability, production operations, and dealership integration if real appointment confirmation is required.
