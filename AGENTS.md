# Adaptive UI engineering workflow

## Scope and design

Use the latest Adaptive UI mockups as the design source of truth. Identify the relevant screens and states before implementing a change. Raise gaps or conflicting requirements with the engineering manager.

The agreed architecture is a mobile-only chatbot, a FastAPI backend, CSV-backed domain tools, and two application agents. Agent 1 curates the answer using domain tools. Agent 2 selects UI functions, maps data to their inputs, and attaches returned React code. See README.md for the flow and proposed response contract. Resolve the remaining framework and runtime choices before introducing them. Run project commands and tests locally. Cloud execution and deployment are outside the current project scope.

Preserve complete raw tool results through the handoff to Agent 2, including image URLs and nested metadata. FastAPI must retain and attach those results independently of Agent 1's prose. Keep the wording and order of surrounding text when converting a section into UI.

CSV stores vehicle research data. Tool discovery metadata uses the YAML manifests in `registries/`, with JSON Schema input contracts and bindings to local Python or React implementations when available. The domain registry enables `search_cars` and the UI registry enables `render_car_list`. Preserve source URLs, check dates, actual model years, media applicability, and offer expiry when loading the CSVs. Consult `data/mazda/us/2027/coverage.csv` for unresolved research areas.

## Roles

- **Engineering manager** defines acceptance criteria, scopes work, coordinates handoffs, resolves dependencies, and reviews the integrated result.
- **UI** interprets the mockups, confirms interaction states and responsive behavior, and identifies accessibility requirements.
- **Frontend** implements approved UI behavior and integrates with agreed interfaces.
- **Backend** implements FastAPI orchestration, CSV-backed Tool Registry functions, and contracts that preserve raw results through the agent handoff, including validation and error behavior.
- **AI** defines and evaluates Agent 1's tool use and response curation and Agent 2's UI selection and data mapping, using local evaluation and documenting limitations.
- **QA** verifies acceptance criteria against the mockups and checks data preservation, image associations, text preservation, regressions, accessibility, and relevant edge cases.
- **DevOps** maintains reproducible local setup and verification commands.

## Handoffs

1. The engineering manager records the goal, relevant mockups, acceptance criteria, dependencies, and the roles needed.
2. For work that needs delegation, the engineering manager may spawn the relevant subagents. Assign each a bounded task and clear ownership of files to avoid overlapping edits. Agree on interface contracts before parallel implementation.
3. Each subagent reports changes, verification performed locally, and open decisions or blockers.
4. The engineering manager integrates changes, coordinates QA, and verifies the result locally against the acceptance criteria before reporting completion.
