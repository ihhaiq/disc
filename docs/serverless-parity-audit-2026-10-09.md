# Serverless vs main — scoped parity audit (2026-10-09)

## Scope and source
Repository: `ihhaiq/disc` — `main` (Python reference) vs `serverless` (V8 JS). No changes to `main`.

## Confirmed source-text parity
Compared the 108 Python `texts.py` string constants and the 92 `locales/en.py` dictionary strings with the checked-in `tgcloud/lib/original-texts.js` snapshots:
- Arabic: **108/108 exact strings; 0 missing, extra, or differing values**.
- English: **92/92 exact strings; 0 missing, extra, or differing values**.
This is **source-data equivalence only**. It does not prove that every handler uses the right key or that formatted messages display identically.

## User-facing fixes on this pass
- Every one of the 13 disc styles now references the original Python `BTN_VINYL_*` text key (including intentional whitespace labels and custom emoji IDs).
- Main-menu and wizard color keyboards now use the translated original keys; wizard styles use `primary` and no selected badge; main-menu current style uses `success`.
- Rotation labels now use the five `SPEED_LABEL_*` strings from Python, preserving original spacing and localization; menu labels use `BTN_VINYL_COLOR_MENU`.
- Disc preview button uses original label and preview custom emoji ID.
- Recreated the default Python developer menu labels/order and restored direct `dev_limits:back`, `dev_whitelist:back` and `dev_text:back` routes. Developer-edited labels are resolved dynamically.
- Restored the original hard-coded customize header and `MSG_VINYL_COLOR_INFO` text in the settings/color views.
- Restored `MSG_QUEUE_CANCELED_EDIT` and `MSG_QUEUE_CANCELED_ANSWER` during wizard cancellation. Group cancel attempts to delete the control message.
- Channel cover-photo replies now find the durable matching `ownerId=0` wizard by its prompt, then proceed to segment or confirmation. `handlers/channel_post.js` forwards photo updates.

## Executed isolated JavaScript checks
These checks executed the **actual GitHub module source** with in-memory dependency mocks, not Telegram's runtime:
- Exact 108/108 Arabic and 92/92 English source data comparisons: passed.
- Catalog and keyboard behavior: 13 IDs, original speed labels, default selected style, group-start label, wizard button state, preview emoji and developer menu: passed (6 automated parity cases total, including snapshots).
- Wizard custom color -> speed -> image, cancellation and channel cover-photo replies: passed (3 mocked runtime cases).
- Previously exercised nested Telegram entity formatting, UTF-16 emoji offsets, unsafe-link escaping, rich-block capture: passed (4 cases).
- All deployable module relative imports and JS syntax were checked in prior source audits, but are not evidence of SDK compatibility.

Reproducible Node tests committed: `tests/serverless/main-parity.test.mjs`, `tests/serverless/logic-parity.test.mjs`, plus existing `tests/serverless/*.test.mjs`.
Use `npm run check` (Node 22+) locally to run syntax/import checks and the full Node test suite.

### GitHub Actions state (not green)
GitHub Actions workflow `Serverless static checks` shows **failure**, with zero reported job steps and an unassigned/empty runner name for inspected runs. GitHub job-log download returned 404. This cannot be honestly treated as a completed Node CI execution or proof of a program-test failure; inspect Actions and runner availability separately. A successful CI run remains required.

## Not 1:1
- **Video engine and progress**: no working JavaScript renderer, audio encoder, 3-second preview, or Video Note. `RENDERER_ENABLED=false` intentionally disables purchases and output.
- **Quick creation**: since rendering is not implemented, the original immediate job-launch behavior cannot complete.
- **Rich-message custom text variables**: string defaults are identical, but structured-media/blocks in **individual developer overrides** still lack full Python fidelity; help's rich-message path is only source-level verified.
- **Group/channel UX**: real bot permissions, ephemeral-message behavior, owner/admin interactions and photo delivery have not been tested against live Telegram updates.
- **Payments**: no live Stars checkout, receipt reconciliation or ledger idempotency proof on Telegram Cloud.
- **State migration**: no `data/` JSON -> SQLite migration of existing users/subscriptions/custom texts; no production schema migration.
- **Configuration**: `DEVELOPER_ID` defaults to 0 on this branch, so developer-only flows require configuration before live testing.

## Deployment
**NOT deployed to Telegram Cloud.** The execution environment has no linked Telegram Cloud CLI access token or `.tgcloud/credentials`, no usable network to install the CLI or clone the repo, and no connected Telegram Cloud deployment integration. The user authorized deployment, but the technical prerequisites are absent. Publishing an incomplete Video Note bot to a production bot would also replace working Python functionality with a disabled renderer; test on a separate bot first.

Required gated verification when project authentication is available:
1. `git switch serverless && npm install && npm run check`
2. In a **test bot** project directory only, `npx tgcloud login` (CLI token from BotFather Serverless CLI Access, never commit tokens).
3. `npx tgcloud status && npx tgcloud diff && npx tgcloud run handlers/message '{chat:{id:123,type:"private"},from:{id:123},text:"/start"}'`
4. Review/test schema migration separately with `npx tgcloud migrate --dry-run` (where supported), then `push` and `migrate` only for the approved test bot.
5. Test the original start/customize/whitelist/help/photo/group/channel flows and inspect platform logs before any production cutover.
