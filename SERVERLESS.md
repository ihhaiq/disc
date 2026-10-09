# Telegram Serverless port — engineering status

This branch retains the original Python implementation from `main` for reference.
The new Telegram-hosted V8 backend is under `tgcloud/`; `main` is unchanged.

## Confirmed compatibility boundary

The original product is **an image/video processing bot**. Python uses Pillow to composite cover art and FFmpeg/ffprobe for rotating the disc, trimming audio, encoding H.264/AAC video notes (up to 60 seconds) and 3-second previews.

Telegram Serverless 0.2.0 accepts plain JavaScript modules and built-in `sdk`; it **does not provide a filesystem, Node.js processes, Python, FFmpeg, Pillow or npm packages at runtime**. A direct port of these CPU-heavy media functions is not executable. In particular, merely calling `api.sendVideoNote` cannot convert incoming audio into an MP4 video note.

Do not claim this branch has 1:1 parity until an equivalent renderer is implemented and exercised against output fixtures. The Python processors under `main` are the existing gold-standard output contract.

## Implemented (source files created and pushed)

- `tgcloud/schema.js`: user prefs, daily usage, paid color flags, whitelist, durable sessions, purchase receipts, editable strings and help drafts.
- `tgcloud/lib/catalog.js`: 13 style identifiers, shadow filenames, disc filenames, custom emoji IDs, special KISS hole size and all 5 rotation options.
- `tgcloud/lib/i18n.js` and `original-texts.js`: 108 original Arabic and 92 original English text variables, key compatibility, and developer-editable overrides.
- `tgcloud/lib/keyboard.js`: start/group/deep-link, style/speed/customize and wizard navigation; conditional cover-image skip and paged minute selection beyond 20 minutes.
- `tgcloud/lib/state.js`: durable preference/settings access and subscription state.
- `tgcloud/lib/wizard.js`: audio intake, private/group/channel session keys, preview/final confirmation interface, alternate cover image and minute selection.
- `tgcloud/lib/admin.js`: whitelist, paid style flags, **13-disc developer keyboard**, persisted disc-menu photo, paginated Arabic/English text-variable browsing, bilingual `/search`, `/edit`, escaped current-value preview; still missing complete Rich Message variable editing parity.
- `tgcloud/lib/help.js`: draft, preview, publish, add/remove URL buttons, and Telegram `sendRichMessage` delivery of stored HTML or structured Rich Message blocks with HTML fallback. This API path is not live-tested and full Python editor parity remains unverified.
- `tgcloud/handlers/*.js`: message, callback, channel posts and Telegram Stars pre-checkout.
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
