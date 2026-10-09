# Telegram Serverless port — engineering status

## Current status: 2026-10-09 message/state implementation

The message and state routes have now been tested by loading the real ESM modules with a substituted Telegram SDK transport and executing SQL against actual SQLite. This covers start/help/settings, the creation wizard, prompt ownership, stale and concurrent callbacks, group/channel cover replies, cancellation, quota handling, developer editing, Rich Message/media preservation, help publishing, and receipt deduplication. Numeric rendering capability is still unproven.

Read [the Arabic setup and test guide](docs/serverless-testing.md) for CLI 0.2.0, the new additive schema fields, and a manual Telegram test matrix. [Parity evidence](docs/video-engine/parity.md) states the remaining gaps. [P0 feasibility](docs/video-engine/feasibility.md) and the isolated capability-probe generator are implemented; **the video renderer is not**.

`npm run check` now runs syntax/import validation plus parity, SQLite-backed behavior, and diagnostics tests. The CLI is pinned to 0.2.0 with a lockfile. GitHub Actions uses the same command. Node 22.13+ is required for the local SQLite harness; runtime modules still have no Node imports or npm dependencies.

No Telegram deployment/migration or successful Video Note proof was performed. `RENDERER_ENABLED=false`; new Stars sales are closed. Existing valid receipt handling remains durable. The historical sections below describe the earlier source-only checkpoint and are superseded by this paragraph for the messaging work.

This branch retains the original Python implementation from `main` for reference.
The new Telegram-hosted V8 backend is under `tgcloud/`; `main` is unchanged.

## Confirmed compatibility boundary

The original product is **an image/video processing bot**. Python uses Pillow to composite cover art and FFmpeg/ffprobe for rotating the disc, trimming audio, encoding H.264/AAC video notes (up to 60 seconds) and 3-second previews.

Telegram Serverless 0.2.0 accepts plain JavaScript modules and built-in `sdk`; it **does not provide a filesystem, Node.js processes, Python, FFmpeg, Pillow or npm packages at runtime**. A direct port of these CPU-heavy media functions is not executable. In particular, merely calling `api.sendVideoNote` cannot convert incoming audio into an MP4 video note.

Do not claim this branch has 1:1 parity until an equivalent renderer is implemented and exercised against output fixtures. The Python processors under `main` are the existing gold-standard output contract.

## Implemented (source files created and pushed)

- `tgcloud/schema.js`: user prefs, daily usage, paid color flags, whitelist, durable sessions, purchase receipts, editable strings and help drafts.
- `tgcloud/lib/catalog.js`: 13 style identifiers, shadow filenames, disc filenames, custom emoji IDs, special KISS hole size and all 5 rotation options.
- `tgcloud/lib/i18n.js` and `original-texts.js`: **108/108 exact Arabic and 92/92 exact English source strings verified against main**; key compatibility and developer-editable overrides. This is a data comparison, not proof of all runtime messages.
- `tgcloud/lib/keyboard.js`: verified original menu/developer/wizard button labels and styles from canonical Python text keys, emoji IDs, five speeds, conditional cover-image skip and paged minute selection beyond 20 minutes. Modified paging is not 1:1 for files exceeding 20 minutes.
- `tgcloud/lib/state.js`: durable preference/settings access and subscription state.
- `tgcloud/lib/wizard.js`: audio intake, private/group/channel session keys, preview/final confirmation interface, alternate cover image and minute selection.
- `tgcloud/lib/admin.js`: whitelist, paid style flags, **13-disc developer keyboard**, persisted disc-menu photo, paginated Arabic/English text-variable browsing, bilingual `/search`, `/edit`, escaped current-value preview; still missing complete Rich Message variable editing parity.
- `tgcloud/lib/help.js`: draft, preview, publish, add/remove URL buttons, and Telegram `sendRichMessage` delivery of stored HTML or structured Rich Message blocks with HTML fallback. This API path is not live-tested and full Python editor parity remains unverified.
- `tgcloud/handlers/*.js`: message, callback, channel posts (audio and cover-photo replies) and Telegram Stars pre-checkout. Actual Telegram Cloud handler behavior is unverified.
- `tests/serverless/*.test.mjs`: static source/architecture invariants.
- API payment charging stays **disabled** while rendering is unavailable. Incoming valid payment receipts are deduplicated and credited; there is no charge for a failed or unavailable render.

## Not at parity

1. **Blocker:** Audio composition, rotating disc, video-note encoding and 3-second preview require a compatible rendering runtime.
2. **Blocker:** Disc PNG images are not deployable as executable modules, and no binary renderer consumes them on this branch.
3. **Missing:** Original worker queue, cancellation of live FFmpeg jobs, render progress and the adaptive bitrate/time-out safeguards.
4. **Missing:** Legacy rich-message InputRichMessage block/emoji semantics in editable help.
5. **Partial:** Developer screens, photo upload and paginated text editor were added. Structured Rich Message help drafts now persist and use `sendRichMessage`. Still missing full `main` rich formatting/editing of individual override texts (incl. rich block/media semantics), round-trip media fixtures, and exact parity of all menu wording and styles. The complete 200 original text variables are present but not all routes use them.
6. **Missing:** End-to-end group/channel permission and reply-to-photo cases verified against actual Telegram updates.
7. **Missing:** Migration of existing JSON state in `data/` to the new database.
8. **Missing:** Live SDK integration and end-to-end payment webhook/idempotency tests. Source-level JavaScript syntax compilation and targeted pure formatting tests passed locally via isolated V8 evaluation on 2026-10-09; GitHub Actions results and real tgcloud SDK tests were not available. Syntax/unit checks do NOT prove the Telegram API accepts `sendRichMessage` payloads or photo/menu routes.
9. **Missing:** Verified live `tgcloud push`, `migrate` and `run` smoke tests.

## Local commands

```bash
git checkout serverless
npm install
npm run check
node --test tests/serverless/*.test.mjs
npx tgcloud login
npx tgcloud status
npx tgcloud diff
# Deployment ONLY when the render gate and database migration are reviewed:
npx tgcloud push
npx tgcloud migrate --dry-run
```

Configure `DEVELOPER_ID` in `tgcloud/lib/config.js` before admin testing.
Do not enable `RENDERER_ENABLED` as a shortcut: a true encoder must first be integrated and tested.
Avoid deploying the incomplete port to the production bot.

## Next engineering decision

To restore 100% media parity, either (a) Telegram adds a supported native media processing interface, or (b) an approved external renderer runs FFmpeg/Pillow with signed, secure job transport and no credentials in git. The second option requires independent hosting for *video encoding*; the Telegram bot interactions and SQLite remain on Telegram Serverless. The user has not approved any external renderer for this repository, so none has been provisioned.

Upstream source: https://blogfork.telegram.org/bots/serverless

## Agent implementation guide

See [`AGENTS.md`](AGENTS.md) for coding rules and [`AGENTS_VIDEO_ENGINE.md`](AGENTS_VIDEO_ENGINE.md) for a stage-gated from-scratch JavaScript rendering research plan. The video engine has **not** been built or validated.

## 2026-10-09 scoped parity pass
- Added `tests/serverless/main-parity.test.mjs`, `tests/serverless/logic-parity.test.mjs`, `scripts/check-serverless.mjs`; `npm run check` covers all module syntax/imports and Node tests.
- **9/9 new cases executed in isolated JavaScript with mocked SDK passed**. Original text values verified byte-for-byte (108 Arabic + 92 English). This is not a complete local `npm` or Telegram Cloud run.
- GitHub Actions workflow runs are **failing without any surfaced steps**, and logs were inaccessible. CI remains red; investigate runner/workflow environment. See [scoped audit](docs/serverless-parity-audit-2026-10-09.md).
- **Cloud deployment still not performed.** No linked Telegram Cloud CLI credentials are available here. Do not claim deployed or full parity, and do not replace the live Python video-producing bot with a branch where `RENDERER_ENABLED=false`.
