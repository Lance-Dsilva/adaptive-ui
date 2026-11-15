# Chat response presentation contract

Implemented 2026-11-14 from the UI team's screenshot review. The Aurora Light theme remains the visual reference.

The API returns one ordered `blocks` array. Each block has an ID stable within its turn; the application assigns purpose and permitted actions independently of model text. Text is not styled according to its array position. Complete raw tool results and registered card props remain preserved through the curator/presentation pipeline.

| Type | Fields | Presentation |
| --- | --- | --- |
| text | id, role, text | answer: 17/24 semibold; body: 16/24; notice/status: 14/20 |
| context | id, items | Informational, wrapping chips immediately before the affected card or empty state |
| ui | id, role=card, component, props, code, fallback_text | Existing registered white card; readable fallback preserves neighboring order |
| actions | id, actions | Up to two buttons; each action has id, label, message and optional compare boolean |
| disclosure | id, title, text | Native details/summary, collapsed by default |

Standalone greetings receive the short greeting, one supporting sentence, Explore SUVs and Compare models actions, and About this catalog disclosure. A greeting combined with a request goes directly to the request.

Context labels show year, requested models, body style, drivetrain, price ceiling and powertrain. The catalog treats max MSRP as inclusive, so the visible label says “Up to $40,000 MSRP.” Chips are not dismissible controls. Clear budget emits a self-contained query for the originating result's other filters; it removes only the price ceiling. Suggested actions and their retries bind to that turn's history rather than later unrelated turns. Unsent suggestions are excluded from the model transcript.

Price and availability qualifiers remain visible alongside results. Source dates and complete financing terms remain in their existing card locations/disclosures. The vague fixed footer has been removed. Loading, failed requests and retry-in-place continue to use explicit states.

## Verification

- 74 backend tests passed, including contract shape, stable IDs, standalone/compound greetings, contextual empty results and executable clear-budget actions.
- 44 frontend tests passed; production bundle passed. Added coverage for role-based typography, block order/fallback, maximum action count, originating-turn history and transcript serialization.
- Local browser: greeting actions/disclosure, comparison selection launch, budgeted SUV query, empty PHEV follow-up, and Clear budget preserving year/body/powertrain all verified.
- 320 px and 390 px layouts fit without document/reply/context/action horizontal overflow; composer visible. Physical mobile keyboard, enlarged OS text and VoiceOver remain untested.
- Calculated minimum contrast against theme gradient stop colors and white: primary text 13.94:1, notices 5.93:1, violet focus/action color 6.38:1, control border 3.76:1. Disabled-control opacity and third-party media were not part of these ratios.
- React checklist review: extracted stable component definitions; native disclosures and buttons; no HTML/code evaluation of model text; existing cancellation and error boundaries retained; no new network waterfall.

![Greeting](../verification/chat-greeting.jpg)

![Context and clear-budget result at 320 px](../verification/chat-context-320.jpg)

## UI team implementation review

The UI team accepted the greeting hierarchy, wrapping context chips and retained-filter flow. Its three additional findings were fixed and regression-tested with API configured and absent: MSRP-qualified budget searches remain discovery, standalone greetings preserve shopping context, and fractional budgets show their actual cutoff. Browser retesting confirmed the MSRP query and greeting-between-follow-ups cases. Clear-budget generated messages use readable plural body-style labels.
