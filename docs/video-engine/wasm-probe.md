# Isolated WASM encoder candidate

Status: locally encoded and independently decoded; Telegram execution/send remains pending. This is a feasibility experiment, not the production renderer.

## Evidence

Operator-provided Telegram results on 2026-10-10: WebAssembly exists and a synchronous empty Module/Instance succeeds (3 ms); OffscreenCanvas, VideoEncoder, AudioEncoder, VideoDecoder and AudioDecoder are undefined. The original combined diagnostic returned HTTP 500, whereas a trivial handler returned `{ok:true}`. The reason for that diagnostic failure remains unestablished.

The new candidate compiles synchronously, uses no Node/browser loaders, workers or Canvas, and replaces the upstream H264 dynamic JavaScript function builders with closures. A local restricted V8 context provides neither Node globals nor filesystem/network/timers, and prohibits string code generation. WASM code generation remains enabled. The encoder's filesystem is an in-memory implementation within that isolate, not host filesystem access.

Local independent validation with FFprobe/FFmpeg succeeded:

- Genuine AVC/H.264, 640×640, 30 frames at 30 fps, duration 1.000 s.
- Genuine mono AAC-LC, 48 kHz, duration 1.000 s after a 2,048-sample priming edit.
- Rotating synthetic colored marker; decoded frame checks confirm movement.
- Synthetic 440 Hz tone; decoded estimate 440.625 Hz, RMS 0.2157. This is not user audio decoding or trimming.
- MP4 size 81,391 bytes. Latest local restricted-context encode elapsed 924 ms; this is NOT a Telegram performance measurement.
- H264 WASM heap 16 MiB and AAC heap 4 MiB. These are heap buffers, NOT measured peak isolate memory.

WASM binaries come from integrity-pinned h264-mp4-encoder 1.0.12 and @audio/encode-aac 1.2.1. Codec binary bytes are unchanged. The generated project retains exact upstream archives, notices and licenses (MIT/public-domain/MPL 1.1 for the video stack; MIT/FDK-AAC for audio). Redistribution of the AAC build must respect its upstream license/patent terms.

## Prepare locally

From the `serverless` checkout, use a NEW absolute destination. Paths with spaces were tested locally. Windows-specific execution remains to be validated.

```bat
npm run prepare:wasm-probe -- "C:\Users\haedr\Desktop\disc-wasm-encoder-probe"
```

This downloads pinned packages using npm, verifies archive SHA-512 before extraction, and creates an unlinked project. It never copies credentials, deploys modules, migrates data or sends a Telegram message. Existing targets are refused. Production modules remain unchanged.

Optional local validation requires Node 22.13+, FFmpeg and FFprobe:

```bat
node --experimental-vm-modules scripts/validate-wasm-probe.mjs "C:\Users\haedr\Desktop\disc-wasm-encoder-probe"
```

The verifier writes a NEW `proof.mp4`, refuses to overwrite an existing file, executes the modules without Node globals/string code generation, and independently checks codecs, duration, decoding, rotation and audible tone.

## Actual Telegram test

From the isolated project, install the pinned CLI and link ONLY the chosen test bot:

```bat
npm install --ignore-scripts
npx tgcloud login
npx tgcloud status
npx tgcloud run handlers/message "{}"
```

Do not push or migrate the probe. Running with `{}` returns encoding metrics and does not send anything. SDK module size limits, host WASM limits, timeout, memory and actual codec execution remain unknown until this succeeds. A Module/Instance-only test cannot answer those questions.

After successful encoding, a separate authorized send can be requested with JSON arguments `{"send":true,"chatId":123456789}` using the actual test chat's numeric ID. The recipient must have started the test bot. The handler sends only one synthetic one-second Video Note. Verify the actual delivered file with independent decode before passing Gate A. No live send was performed by this work.

The managed environment currently has no injected TGCLOUD_TOKEN or linked account: a fresh CLI attempt stopped with `No CLI access token found for this project`. To let the agent execute remote tests, supply the test bot's CLI Access token through the secure TGCLOUD_TOKEN requirement in environment settings (destination cloud.telegram.org), never in chat. Saving a requirement is not credential injection or publication.

## Work after Gate A

Port the original PNG composition and all 13 templates, implement real user audio decoding/resampling/trim, verify three-second previews and 60-second outputs under measured limits, integrate durable jobs/cancellation and commit quota only after successful delivery. Synthetic proof output does not satisfy these requirements. RENDERER_ENABLED remains false and new Stars sales stay disabled.
