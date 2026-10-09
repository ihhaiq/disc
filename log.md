# Vinyl Bot — serverless branch change log

## 2026-10-09 — Initial Telegram Serverless 0.2.0 migration

**Why:** preserve the user-facing features of `main` while moving Telegram event handling and durable state into the hosted JavaScript/V8 runtime.

**Changes:** introduced `tgcloud/schema.js`, persistent account/session/payment/help/text tables, matching 13-disc catalog, Arabic/English UI, independent callback routes, developer whitelist and paid-color controls, editable help drafts and a local Node-based test suite with CI. Fixed callback double-answer behavior and kept the render/paywall gate off.

**Parity:** INCOMPLETE. The original production purpose—FFmpeg/Pillow video-note output and low-res previews—cannot be executed in current Telegram Serverless JS. No external backend was created and no paid product was activated. Refer to `SERVERLESS.md` for the explicit gap list.

**Safety:** only `serverless` changed; no modifications to `main`, no production deployments, no database migration, no claims of end-to-end 1:1 parity.

## 2026-10-09 — Compatibility and safety hardening

**Changes:** imported all 108 original Arabic text variables and 92 English translations into `tgcloud/lib/original-texts.js`; linked original keys to the translated UI and extended developer text lookup. Stored the wizard prompt message ID to ensure group cover-image replies target the correct session. Added selected-speed UI state and documented missing media capabilities on all relevant controls. Removed two unnecessary update handlers.

**Payment safety:** immutable Telegram Stars receipts are deduplicated; user premium expiry can be reconciled from recorded receipts, including after an interrupted request. New invoices and pre-checkout are still rejected until rendering is genuinely supported.

**Validation:** the V8 JavaScript parser accepted all 16 deployable modules after stripping ESM import/export wrappers for syntax-only analysis; all relative imports resolved to files in the branch. The static CI workflow was committed but no successful runner result or live SDK execution was observed. No claim of 1:1 parity or successful Telegram deployment.

## 2026-10-09 — Speed selection UI bug fix

**Change:** corrected the Serverless speed callback to render the newly selected rotation speed instead of the stale pre-update user preference. The preference is still saved through the existing database update path.

**Verification:** source-level review and exact targeted replacement; no live Telegram Serverless test or production deploy was performed. Overall feature parity remains incomplete, especially FFmpeg/Pillow rendering. Main was not modified.

## 2026-10-09 — Agent plan, developer panel, rich help and usability parity

**Scope:** `serverless` branch ONLY; `main` unchanged.

### Added
- `AGENTS.md` and `AGENTS_VIDEO_ENGINE.md` with a gated plan for a native JavaScript engine: runtime feasibility proof, video encoder/muxer proof, golden-frame/audio checks, 13 templates, all speeds and durations, 3-second preview and 60-second Video Note; forbid silently introducing external hosting.
- `tgcloud/lib/dev-text-utils.js` plus unit tests: Telegram UTF-16 entity offsets, nested bold/italic, safe link markup, custom emoji, Rich Message extraction and preservation of blocks.
- Reworked developer UI: original 13-disc menu, Arabic/English text-variable pages, value previews, bilingual `/search` and `/edit`, validation and HTML escaping. Disallowed editing non-string label arrays.
- Developer menu-photo upload stored in SQLite-backed overrides, displayed in disc color menu; photo caption can be edited when switching language or choosing a disc.
- `/help` draft editing preserves Telegram rich blocks (when supplied) and attempts `sendRichMessage` with HTML compatibility fallback. Added button removal in the draft.
- Long-audio minute choice now has pages; missing-thumbnail prompts no longer display a nonfunctional Skip button.

### Fixes
- Avoid duplicate callback acknowledgements for developer/help alerts.
- Fall back to safe escaped text for malformed HTML in developer-customizable message paths.
- Preserve correct selected speed and selection markers in the main settings keyboard.

### Verification and remaining gaps
- Checked JavaScript syntax for affected modules by compiling their bodies in an isolated V8 engine after stripping ESM wrappers (NOT a runtime SDK test).
- Executed targeted pure-function assertions for nested Telegram formatting, emoji offsets, unsafe URLs and rich-block capture. Tests were also committed for Node CI; successful CI execution was not observed here.
- Still **not 100%**: FFmpeg/Pillow replacement and actual Video Notes absent; exact rich-message editing of all variables, legacy JSON migration, end-to-end tests, production SDK integration, group/channel flows and Stars webhook tests remain. No `tgcloud push` or production database migration was performed.

### Final command routing and regression checks (2026-10-09)
- Restricted `/help` and `/start` routing to exact Telegram commands rather than accepting `/helper` or `/startfoo` prefixes; preserves the `/start help` deep link.
- Added `tests/serverless/ui-parity.test.mjs` to guard developer UI, stored disc menu photo, rich help, paginated minute selection, and inactive payment gate.
- Reviewed all 17 `tgcloud/*.js` modules on the branch with isolated V8 syntax compilation and cross-checked all relative imports; **0 syntax or missing-import errors** in this check. This does not substitute for production execution or the GitHub Actions runner.

## 2026-10-09 — Canonical main labels and isolated JS logic tests

- Compared `main/texts.py` (108 values) and `main/locales/en.py` (92 values) against `tgcloud/lib/original-texts.js`: **200 exact matches; zero missing/differing strings**. This covers source texts only, not all runtime routes.
- Mapped 13 disc styles to original text keys; restored original button labels, spacing, emoji IDs, active/wizard styles, speed labels, developer menu and settings/color headers. Reason: previous hard-coded text variants did not match Python.
- Fixed wizard cancellation texts and channel cover-photo reply handling; updated `channel_post` handler. Reason: canceled jobs showed an expiry error and the channel photo path was unreachable.
- Added executable Node tests `main-parity.test.mjs` (6 cases) and `logic-parity.test.mjs` (3 cases), and a complete local syntax/import checking script. Updated `npm run check` to invoke full checks and tests. Executed all 9 new tests in isolated JavaScript with mocked SDK; **9/9 passed**. The earlier 4 pure formatting cases also passed in isolated JS.
- The GitHub Actions runs remain **red** with empty job steps and unavailable log downloads, so actual CI success remains unverified; no valid `npm run check` execution on a checked-out full repository is claimed.
- **No Telegram Cloud deployment**: environment has no cloud CLI credentials/project login, no Telegram deployment integration and cannot clone/install via outbound network. Renderer still off; no production migration, checkout or replacement of the Python bot.
- Full detail: `docs/serverless-parity-audit-2026-10-09.md`.
# 2026-10-09 — Serverless message/state behavior and P0 discovery

- Compared `main` media functions and conversational routes; changed only the `serverless` worktree. The Python renderer and assets remain unchanged.
- Added session revisions and SQLite compare-and-swap transitions, prompt/chat binding, duplicate audio protection, failed-presentation rollback, cancellation at every stage, and private/group/channel cover isolation.
- Routed canonical bilingual texts and formatted numeric placeholders correctly. Added Rich Message override persistence, media normalization, RTL, validation before save, caption-aware edits, and compatibility fallbacks that do not conceal rate-limit/network errors.
- Completed current-value text search, editor cancellation, paginated whitelist access, help drafts/buttons/publishing, and the disabled-sales/payment-receipt paths. Commands addressed to another bot are ignored.
- Replaced the wizard's source-stripping test harness with real ESM loading and real SQLite. Added end-to-end mocked conversational tests; corrected a stale static assertion that expected developer routing inline instead of delegated to `admin.js`.
- Added `tgcloud/lib/video/diagnostics.js`, isolated probe-project preparation, P0 feasibility/parity reports and `docs/serverless-testing.md`. An actual CLI run was blocked by missing CLI access credentials; there is no claim of a generated Video Note.
- Pinned CLI 0.2.0 and added its lockfile; CI runs the same `npm run check` suite as local verification.
- Verification: 19 deployable modules passed syntax/import checks; all 62 local tests passed, including late older audio updates. Live Telegram SDK/API/permission behavior and video encoding remain pending.

## 2026-10-09 — Usability follow-up: legacy import and replay-safe developer changes

- Rechecked the official runtime documentation, CLI 0.2.0 SDK and current cloud readiness. No native H.264/AAC API is documented and no Telegram Cloud identity is linked. A fresh isolated `tgcloud run` still returned `No CLI access token found for this project`. Gate A remains BLOCKED; this is not proof that pure JS encoding is impossible. No external renderer was introduced and the render/payment gates were not changed.
- Added an offline importer for the exact three JSON stores persisted by main: usage/subscription/whitelist/paid styles, bilingual custom texts and menu image, published/help drafts with rich blocks/buttons/RTL. It validates inputs before generating private review files, never prints user values, never logs in/deploys/executes SQL during preparation, and uses insert-only preservation of existing rows.
- Added local transaction SQL and a separate CLI project with bounded, independently replay-safe import batches. Failed batches can rerun from the same start; remote operations are explicitly not claimed to be one transaction. Existing rows are skipped and Python memory-only preferences cannot be recovered. File IDs remain bot-specific. No actual main data was copied or imported.
- Added `premium_base_until` so new receipts extend imported subscriptions once. Expiry repair uses a monotonic SQL update; an older concurrent calculation cannot shorten a newer expiry. Legacy owner zero data is preserved without allowing invalid zero whitelist/draft users.
- Replaced paid-style toggles with desired-state/revision callbacks and conditional SQLite updates. Replayed, concurrent, malformed and old unversioned callbacks cannot reverse settings.
- Added help document revisions and compare-and-swap writes; draft creation no longer resets a concurrent existing draft. Old/repeated deletion buttons cannot remove a different button that shifted into the same index.
- New fields are additive only: `vinyl_users.premium_base_until`, `vinyl_paid_colors.revision`, `vinyl_help_docs.revision`. Production schema migration was not performed.
- Added migration and replay/concurrency tests, including deliberate late subscription writes and interrupted import retry. Updated setup/import/parity/feasibility documentation and removed obsolete current-status statements from SERVERLESS.md.
- Verification: `npm run check` passed 20 runtime modules and 80 tests; `git diff --check` passed. Actual Telegram SDK/import/API behavior and video rendering remain unverified. The branch cannot yet be used to generate videos.

## 2026-10-10 — Windows test compatibility and live runtime recheck

Fixed developer configuration injection in the SDK harness to use path.basename, supporting both Windows and POSIX separators. Converted file URLs with fileURLToPath before spawning the legacy import generator, preventing Windows C:\C:\ paths. POSIX mode assertions remain enforced on POSIX; Windows uses ACLs, so the test does not equate mode bits with access control. No bot runtime behavior, renderer gate, payments or production deployment changed.

Validation: npm ci --ignore-scripts; npm run check: 20 deployable modules, 80 tests passed on Linux/Node 24.19.0. No Windows execution environment was available; a native Windows rerun is still needed. An isolated diagnostic project was prepared and tgcloud run exited with No CLI access token found for this project. Current managed environment has no TGCLOUD_TOKEN binding. Video generation remains blocked at platform measurement/Gate A; no encoded Video Note is claimed.
