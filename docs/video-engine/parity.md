# Serverless parity evidence

Local checks load the real ESM modules into independent VM contexts, substitute SDK transport, and execute persistence and compare-and-swap SQL against **real SQLite**. The database DSL adapter is a test substitute, so these checks do not establish compatibility with Telegram's actual SDK. All Telegram runtime and API results remain unverified until the operator runs them.

| Requirement | Local evidence | Telegram result |
| --- | --- | --- |
| Original Arabic/English messages | Exact comparisons of 108 AR + 92 EN constants; format precision and HTML-safe parameters | Pending |
| 13 templates / 5 speeds | Catalog and keyboard tests including KISS ratio 0.39 | Pending |
| Start/help/language/settings | Routed messages, persisted preferences and photo captions | Pending |
| Mode/color/speed/image/minute/confirmation | Full SQLite-backed transition tests, conditional cover skip and minute paging | Pending |
| Cancellation/session expiry | Durable deletion, TTL and cancellation from every stage | Pending |
| Duplicate/old/concurrent wizard callbacks | Prompt/chat matching and revision compare-and-swap; retry after presentation errors | Pending |
| Groups/channels | Owner/admin authorization, reply-to-prompt cover matching and private/group separation | Actual chat permissions and update delivery pending |
| Developer controls | Private authorization, menu image, paginated whitelist; desired paid style state with revision CAS rejects repeated/stale/concurrent buttons | Pending |
| Text editor | Canonical variable pages, current-value search, markdown/emoji validation and rejected-save behavior | Actual HTML validation pending |
| Rich text/media/RTL | Blocks retained; input media normalization; SDK request payloads and compatibility fallback | Actual send/edit/media acceptance pending |
| Help builder | Draft/text/buttons/delete/preview/publish, editor cancellation, revision-bound deletion and CAS writes prevent stale-index deletion/lost changes | Pending |
| Payment receipts | Validated ownership/currency/amount, unique ledger, duplicate retry, imported-premium baseline, interrupted-credit repair and monotonic expiry updates | Actual payment updates pending; sales closed |
| Usage limit/reset/exemptions | Local SQLite tests; render attempts never charged | Actual successful-render accounting pending |
| Static module restrictions | Syntax/import checks for every deployable JS module | Actual SDK compilation pending |
| Runtime capability discovery | Negative/support simulations; operator reported synchronous WASM success and absent Canvas/WebCodecs | Full codec candidate run pending; agent CLI account absent |
| Rotating disc composition / golden pixels | Not implemented in JS | Pending |
| Real user audio decode/trim/AAC encode | Not implemented in JS | Pending |
| H.264 encoder / ISO BMFF muxer | Isolated WASM H264 + AAC candidate, JS audio muxer; independent local decode of a synthetic 1-second MP4 | Actual Telegram codec execution/send pending |
| Three/sixty-second output, synchronization | No JS output to inspect | Pending |
| `sendVideoNote` proof / Gate A / Gate B | No successful test | BLOCKED |
| Original worker queue/cancellation/progress | No fake jobs introduced while renderer is absent | Pending renderer integration |
| Migration from Python JSON state | Offline validated plans/SQL/isolated CLI batches for all three actual stores; real SQLite round-trip, interrupted retry and insert-only preservation tested | Actual SDK import pending; no production writes |

Deliberate differences: minute lists page after 20 minutes; every wizard stage offers cancellation; shared photos require a reply to the current prompt; group/channel flows reach a durable confirmation screen while rendering is unavailable. The full output cannot be called 1:1 or 95% complete based on UI tests.

The importer cannot recover language/style/speed that existed only in Python process memory. It preserves existing target rows and reports skipped inserts, rather than silently overwriting them. Telegram file IDs remain bot-specific. See [migration instructions](../legacy-import.md).
