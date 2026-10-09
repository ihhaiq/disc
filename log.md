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
