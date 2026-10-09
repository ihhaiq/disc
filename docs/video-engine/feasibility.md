# Video engine feasibility — P0

Status: **BLOCKED at live runtime evidence / Gate A**. No rotating video with valid audio has been generated inside Telegram or sent as a Video Note by this change. This is not evidence that pure JavaScript encoding is impossible.

## Reference and tooling

- Python/FFmpeg reference: `main` commit `4c5dcdda5376533a9dac02dd31960b7b9e44bee5`.
- Inspected `compose.py`, `processor.py`, `services/job_processor.py`, `vinyl_catalog.py` and `assets/`. They are unchanged from `main` in the starting `serverless` checkout.
- Installed CLI exactly **0.2.0**, pinned with the npm lockfile.
- Primary runtime documentation read on 2026-10-09: [Telegram Serverless](https://blogfork.telegram.org/bots/serverless); packaged SDK reference at `node_modules/@tgcloud/cli/src/templates/docs/tgcloud-sdk.md`.

The reference produces H.264/AAC MP4, 640×640 at 30 fps for full output, and 320×320 at 15 fps for a three-second preview. Output is limited to 60 seconds and the reference enforces 12,582,912 bytes per Video Note. All 13 PNG templates and five rotation settings remain the target.

## Confirmed platform contract

The documented runtime accepts project JavaScript modules and SDK imports, rather than Node processes, a filesystem or npm packages. SDK file helpers expose bytes: download is capped at 20 MB; uploads accept `InputFile`; the SDK's documented general upload limit is 50 MB. Outbound fetch responses have a separate 30 MB cap. These facilities move files; they do not provide a documented H.264/AAC encoder.

The consulted documentation does not specify numeric CPU, wall-clock or isolate memory limits. WebAssembly, OffscreenCanvas and WebCodecs must be measured on Telegram, rather than inferred from local Node. `diagnostics.js` therefore leaves those limits unknown and distinguishes API/config support from actual encoding proof.

## Executable discovery

`tgcloud/lib/video/diagnostics.js` checks availability, a tiny typed-array operation, empty WebAssembly instantiation, H.264 640×640/30fps encoder configuration, and AAC stereo 48kHz configuration. It makes no SDK requests and consumes no user audio. Even supported configurations keep `encodingVerified=false` and `gateA=BLOCKED`.

CLI 0.2.0's baseline **does not run lib modules directly**. `scripts/prepare-video-probe.mjs` creates an isolated project with a temporary runnable handler importing the library. No diagnostic handler is added to the bot. Use the [testing guide](../serverless-testing.md#فحص-قدرات-محرك-الفيديو) to run the probe without deploying.

An actual `tgcloud run` attempt in the isolated project exited with:

```text
Error: No CLI access token found for this project.
```

There is no linked Telegram Cloud account in this execution environment. No production commands were executed. The next result required is the real platform probe output from an account enabled for Serverless.

Rechecked the official Serverless page and packaged SDK on 2026-10-09 during the usability follow-up: no documented Canvas, WebCodecs or H.264/AAC encoding interface was found. The managed environment reported current observations with no secrets, runtime credentials or outbound identities. A fresh isolated CLI run again exited with `No CLI access token found for this project`. This blocks platform measurement; it does not establish that encoders are impossible in pure JavaScript. No local Node encoder was substituted for a Telegram result.

## Pure JavaScript encoding assessment

PNG decoding, alpha composition, rotation and ISO BMFF muxing are individual engineering tasks. Muxing cannot substitute for valid elementary streams. Without working native codecs, a pure JS path would need a verified audio demuxer/decoder and AAC encoder plus a compressed AVC encoder. No such implementation is present or claimed here; no external renderer was introduced.

Resource lower bounds at 640×640/30fps:

| Buffer | Bytes |
| --- | ---: |
| One RGBA frame | 1,638,400 |
| All RGBA frames for 60 seconds | 2,949,120,000 |
| Uncompressed YUV420 frames for 60 seconds | 1,105,920,000 |
| Stereo Float32 PCM at 48kHz for 60 seconds | 23,040,000 |

Thus retaining every frame is unsuitable. A simple AVC I_PCM strategy still carries roughly 18,432,000 uncompressed pixel bytes for just one second at 30fps before bitstream overhead, exceeding the reference output budget. A usable codec must compress and process bounded batches. These are calculations, not measured Telegram memory or time limits.

## Gate A and next work

1. Run the isolated capability probe on Telegram and record the output and CLI version.
2. Establish numeric runtime constraints using the platform's verified response or documented limits.
3. Select an encoding approach supported by that evidence.
4. Generate one second of a rotating 640×640 picture and valid audio within the isolate; independently decode and inspect tracks and timestamps; send it successfully with `sendVideoNote` on the chosen test bot.

P1–P4 rendering work remains pending. Message/state logic can be tested independently under the revised task scope. Payments and the render gate remain disabled.
