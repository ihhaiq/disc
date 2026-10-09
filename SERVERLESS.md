# Telegram Serverless port — current engineering status

Updated 2026-10-09. Work targets `serverless`; the original Python implementation and assets from `main` are retained unchanged as the reference.

**The port is ready for message/state and data-import testing. It cannot yet create or send a Video Note.** The video encoder, compositor and real audio pipeline are absent. `RENDERER_ENABLED=false`, new Stars sales remain closed, and unavailable render attempts never consume quota.

## Implemented and tested locally

- Canonical bilingual message constants: 108 Arabic and 92 English values match `main` exactly. Formatting, HTML escaping, Rich Message/media preservation and compatibility fallback behavior have local tests; acceptance of actual Telegram API payloads is pending.
- Start/help/language/settings, all 13 disc choices and five speeds; menu photo/caption handling and durable user preferences.
- SQLite creation wizard: mode, style, speed, cover, paginated minute selection, confirmation and cancellation. Ownership, current chat/prompt binding, revision compare-and-swap, session expiry, late/duplicate audio protection, and failed-presentation rollback are tested.
- Private/group/channel routing and cover replies. Real group/channel permission checks remain unverified.
- Private authorized developer controls, text browsing/search/editing, whitelist pages, menu image and paid-style settings. Versioned desired-state buttons prevent duplicate or old clicks reversing newer paid-style settings.
- Help drafts, rich text/blocks/RTL, URL buttons, previews and publishing. Draft writes use compare-and-swap; deletion buttons identify the draft revision so a replay cannot delete a different button at the same index.
- Validated, deduplicated receipt ledger with interrupted-credit repair. Imported premium is a fixed baseline for subsequent purchases; concurrent expiry writes cannot decrease a newer value. This is receipt accounting, not enabled sales.
- [Legacy JSON import](docs/legacy-import.md): offline validation, private review artifacts, SQL for local verification, and an isolated CLI batch project. All three stores actually persisted by `main` are mapped. Existing target rows are preserved; interrupted batches can be rerun. No live or production import was performed.
- [P0 runtime diagnostics](docs/video-engine/feasibility.md) and isolated probe preparation, with no production diagnostic route or fake encoded output.

`npm run check` passes **20 deployable modules and 80 local tests**. Tests load real ESM with substituted SDK transport and execute SQL against real SQLite. This does not prove the platform SDK DSL, API or codec support. CLI is pinned to 0.2.0; local tests require Node 22.13+ while bot runtime modules use no Node or npm dependencies.

## Remaining blockers

1. **Video generation:** reproduce the original PNG composition and rotation, decode and trim real user audio, encode H.264/AAC, mux valid MP4, and send actual three-second previews and up-to-60-second Video Notes.
2. **Runtime proof:** the platform documents byte download/upload, not a native media encoder. WebAssembly/Canvas/WebCodecs and numeric CPU/memory/time limits require actual Telegram measurements. The isolated CLI probe remains blocked by missing CLI access credentials; Gate A and Gate B have not passed.
3. **Render integration:** durable jobs, cancellation while rendering, real progress, resource/size/time safeguards and quota commitment after successful delivery depend on a working renderer.
4. **Live verification:** actual module compilation, SDK/database behavior, rich messages, permissions, receipt delivery and migration batches require a Telegram-enabled test environment. No deployment or production migration was performed.

The full parity status and required evidence are in [parity.md](docs/video-engine/parity.md). There is no verified 95% or 100% completion claim.

## Setup and schema changes

Follow the [Arabic testing guide](docs/serverless-testing.md). Set your numeric `DEVELOPER_ID` in `tgcloud/lib/config.js` before testing admin controls. Keep the render gate false.

New additive fields in this follow-up: `vinyl_users.premium_base_until`, `vinyl_paid_colors.revision`, `vinyl_help_docs.revision`. Review schema migration on your chosen isolated bot before running updated handlers or imports. Earlier additive session mode/revision, rich override and RTL fields remain necessary. No drops or type changes were introduced.

```bash
npm ci --ignore-scripts
npm run check
npm run prepare:video-probe -- /tmp/new-vinyl-runtime-probe
npm run prepare:legacy-import -- /path/to/main/data /tmp/new-vinyl-import
```

The preparation commands only create local artifacts. The temporary import handler must never be deployed: its CLI run operates on the linked account's database, so select and verify the test account first.

## Architectural decision still open

[AGENTS_VIDEO_ENGINE.md](AGENTS_VIDEO_ENGINE.md) requires video generation inside Telegram V8 and forbids silently introducing an external renderer. An external Python/FFmpeg worker could retain the reference output while bot interactions and SQLite stay on Telegram Serverless, but changes that requirement and needs the user's choice. None has been added or provisioned.

The official reference remains [Telegram Serverless](https://blogfork.telegram.org/bots/serverless). Historical investigation and checkpoints are retained in `log.md` and the dated audit documents; this file describes the current implementation.
