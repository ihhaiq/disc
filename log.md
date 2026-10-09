# Vinyl Bot — serverless branch change log

## 2026-10-09 — Initial Telegram Serverless 0.2.0 migration

**Why:** preserve the user-facing features of `main` while moving Telegram event handling and durable state into the hosted JavaScript/V8 runtime.

**Changes:** introduced `tgcloud/schema.js`, persistent account/session/payment/help/text tables, matching 13-disc catalog, Arabic/English UI, independent callback routes, developer whitelist and paid-color controls, editable help drafts and a local Node-based test suite with CI. Fixed callback double-answer behavior and kept the render/paywall gate off.

**Parity:** INCOMPLETE. The original production purpose—FFmpeg/Pillow video-note output and low-res previews—cannot be executed in current Telegram Serverless JS. No external backend was created and no paid product was activated. Refer to `SERVERLESS.md` for the explicit gap list.

**Safety:** only `serverless` changed; no modifications to `main`, no production deployments, no database migration, no claims of end-to-end 1:1 parity.
