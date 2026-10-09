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
