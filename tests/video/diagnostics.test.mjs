import test from 'node:test';
import assert from 'node:assert/strict';
import { inspectRuntime, resourceEstimate } from '../../tgcloud/lib/video/diagnostics.js';

test('missing native APIs are reported without pretending video encoding works',async()=>{
  const report=await inspectRuntime({Uint8Array,DataView});
  assert.equal(report.binary.status,'verified');assert.equal(report.codecs.h264.supported,false);
  assert.equal(report.gateA,'BLOCKED');assert.equal(report.encodingVerified,false);
  assert.equal(report.runtimeLimits.memoryBytes,null);
});
test('even supported H264/AAC configs do not count as end-to-end Video Note proof',async()=>{
  const configs=[];
  const supported={isConfigSupported:async config=>{configs.push(config);return {supported:true};}};
  const report=await inspectRuntime({VideoEncoder:supported,AudioEncoder:supported,VideoFrame:function(){},AudioData:function(){}});
  assert.equal(report.nativeEncoderCandidate,true);assert.equal(configs[0].width,640);
  assert.equal(configs[1].codec,'mp4a.40.2');assert.equal(report.gateA,'BLOCKED');
});
test('codec and WebAssembly exceptions fail closed without logging exception messages',async()=>{
  const report=await inspectRuntime({Uint8Array,WebAssembly:{instantiate:async()=>{throw new TypeError('private data');}},
    VideoEncoder:{isConfigSupported:async()=>{throw new Error('private data');}}});
  assert.equal(report.wasm.status,'error');assert.equal(report.codecs.h264.status,'error');
  assert.equal(JSON.stringify(report).includes('private data'),false);
});
test('resource estimates document why buffering every raw frame is impractical',()=>{
  const report=resourceEstimate();assert.equal(report.frameRgbaBytes,1638400);
  assert.equal(report.bufferedRgbaBytes,2949120000);assert.equal(report.uncompressedYuv420Bytes,1105920000);
  assert.equal(report.stereoFloatPcmBytes,23040000);
  assert.throws(()=>resourceEstimate({seconds:-1}),RangeError);
});
