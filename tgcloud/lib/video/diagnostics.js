// P0 capability discovery only. No SDK calls, user files, rendering, or production flag changes.
function read(root,name) {
  try {return root[name];}catch{return undefined;}
}
const errorName=error=>typeof error?.name==='string'?error.name:'Error';
async function codecProbe(root,name,config) {
  const encoder=read(root,name);
  if(typeof encoder?.isConfigSupported!=='function')return {status:'unavailable',supported:false};
  try {
    const result=await encoder.isConfigSupported(config);
    return {status:result?.supported===true?'supported':'unsupported',supported:result?.supported===true};
  } catch(error) {return {status:'error',supported:false,errorName:errorName(error)};}
}
export function resourceEstimate({width=640,height=640,fps=30,seconds=60}={}) {
  for(const value of [width,height,fps,seconds])if(!Number.isSafeInteger(value)||value<=0)throw new RangeError('Positive integer dimensions, fps and seconds required');
  const frameRgbaBytes=width*height*4,frameYuv420Bytes=Math.ceil(width/2)*Math.ceil(height/2)*2+width*height;
  return {width,height,fps,seconds,frameRgbaBytes,frameYuv420Bytes,
    bufferedRgbaBytes:frameRgbaBytes*fps*seconds,
    uncompressedYuv420Bytes:frameYuv420Bytes*fps*seconds,
    stereoFloatPcmBytes:48000*2*4*seconds};
}
export async function inspectRuntime(root=globalThis) {
  const names=['WebAssembly','WebCodecs','VideoEncoder','AudioEncoder','VideoDecoder','AudioDecoder',
    'VideoFrame','AudioData','OffscreenCanvas','createImageBitmap','Uint8Array','ArrayBuffer','DataView',
    'DecompressionStream','CompressionStream','TextEncoder','performance','process','document'];
  const globals=Object.fromEntries(names.map(name=>[name,typeof read(root,name)]));
  let binary={status:'unavailable'},wasm={status:'unavailable'};
  const Bytes=read(root,'Uint8Array'),View=read(root,'DataView');
  if(typeof Bytes==='function'&&typeof View==='function') {
    try {const bytes=new Bytes(16),view=new View(bytes.buffer);view.setUint32(0,0x01020304,false);
      binary={status:bytes[0]===1&&view.getUint32(0,false)===0x01020304?'verified':'failed'};
    }catch(error){binary={status:'error',errorName:errorName(error)};}
  }
  const Wasm=read(root,'WebAssembly');
  if(typeof Bytes==='function'&&typeof Wasm?.instantiate==='function') {
    try {
      // Eight-byte empty module tests instantiation, not media encoding.
      await Wasm.instantiate(new Bytes([0,97,115,109,1,0,0,0]));wasm={status:'verified-empty-module'};
    }catch(error){wasm={status:'error',errorName:errorName(error)};}
  }
  const h264=await codecProbe(root,'VideoEncoder',{codec:'avc1.42E01F',width:640,height:640,
    framerate:30,bitrate:1400000,avc:{format:'avc'}});
  const aac=await codecProbe(root,'AudioEncoder',{codec:'mp4a.40.2',sampleRate:48000,numberOfChannels:2,bitrate:128000});
  return {schemaVersion:1,globals,binary,wasm,codecs:{h264,aac},resourceEstimate:resourceEstimate(),
    nativeEncoderCandidate:h264.supported&&aac.supported&&globals.VideoFrame==='function'&&globals.AudioData==='function',
    encodingVerified:false,gateA:'BLOCKED',
    remainingProof:['one-second-rotating-640x640-h264-aac-mp4','independent-decode-and-av-sync-check','test-bot-sendVideoNote-success'],
    runtimeLimits:{memoryBytes:null,cpuMilliseconds:null,wallMilliseconds:null},
    note:'Capability discovery is not a rendered video or evidence that Node matches Telegram V8.'};
}
