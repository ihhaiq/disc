# AGENTS.md — ihhaiq/disc / serverless

## Scope and safety
- Work on `serverless` branch, preserve `main` as the Python/FFmpeg reference.
- For media processing read and follow [AGENTS_VIDEO_ENGINE.md](AGENTS_VIDEO_ENGINE.md). No claims of functional rendering without a real Video Note proof.
- For behavior parity compare against `routers/`, `handlers.py`, `keyboard.py`, `help_builder.py`, `limits.py`, `texts.py`, `locales/` and `tests/` on `main`.
- Keep `log.md` updated with exact changes and verification, and maintain `SERVERLESS.md` gaps honestly.
- Telegram Serverless: only ESM `.js` under `tgcloud/{schema.js,handlers,lib,endpoints}`, imports via `sdk` and relative `.js`; no `fs`, `child_process`, npm runtime dependencies or mutable process-global session state. Use SQLite tables for durable per-user actions. CLI 0.2.0.
- Never push to production, migrate production data, activate Stars sales, or alter the `RENDERER_ENABLED` gate without explicit approval and end-to-end tests.
- Developer actions must authorize on every callback/message; escape user-controlled HTML and check callback inputs; do not leak bot tokens.
- Tests: `npm run check`, `node --test tests/serverless/*.test.mjs`, then live isolated `tgcloud run` tests where possible.
