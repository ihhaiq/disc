// Synthetic one-second Gate A candidate, not the production vinyl renderer.
import h264Factory from './h264-core.js';
import aacFactory from './aac-core.js';
import { muxProof } from './mux.js';
export async function renderProof(){
 const started=Date.now();let stage='h264-init',encoder,aac,handle;
 try {
  const module=h264Factory({print:()=>{},printErr:()=>{}});
  // The preparation adapter compiles synchronously; no browser loader or workers.
  encoder=new module.H264MP4Encoder();encoder.width=640;encoder.height=640;encoder.frameRate=30;encoder.kbps=1400;encoder.speed=10;encoder.initialize();
  stage='h264-frames';const frame=new Uint8Array(640*640*4);
  for(let f=0;f<30;f++){
   const angle=f/30*Math.PI/2,c=Math.cos(angle),s=Math.sin(angle);
   for(let y=0;y<640;y++)for(let x=0;x<640;x++){
    const dx=x-320,dy=y-320,r2=dx*dx+dy*dy;const rx=dx*c+dy*s,ry=-dx*s+dy*c;
    const marker=rx>80&&rx<245&&Math.abs(ry)<20;const disc=r2<300*300&&r2>55*55;
    const i=(y*640+x)*4;frame[i]=marker&&disc?245:disc?45:12;frame[i+1]=marker&&disc?90:disc?60:12;frame[i+2]=marker&&disc?35:disc?75:12;frame[i+3]=255;
   }
   encoder.addFrameRgba(frame);
  }
  encoder.finalize();const video=module.FS.readFile(encoder.outputFilename).slice();module.FS.unlink(encoder.outputFilename);encoder.delete();encoder=null;
  stage='aac-init';aac=await aacFactory({print:()=>{},printErr:()=>{}});handle=aac._ae_create(48000,1,64000,2,0);if(!handle)throw new Error('AAC encoder unavailable');const priming=aac._ae_delay(handle);
  stage='aac-samples';const offset=aac._ae_input(handle,48000)>>1;for(let i=0;i<48000;i++)aac.HEAP16[offset+i]=Math.round(10000*Math.sin(i*2*Math.PI*440/48000));
  if(aac._ae_encode(handle,48000)<0||aac._ae_flush(handle)<0)throw new Error('AAC encoding failed');
  const audio=aac.HEAPU8.slice(aac._ae_output_ptr(handle),aac._ae_output_ptr(handle)+aac._ae_output_len(handle));aac._ae_destroy(handle);handle=0;
  stage='mux';const output=muxProof(video,audio,{priming});if(output.length>12582912)throw new Error('Video Note size limit');
  return {bytes:output,report:{stage:'encoded',encodingCandidate:true,width:640,height:640,fps:30,seconds:1,audio:'synthetic-440Hz-tone',video:'synthetic-rotating-marker',outputBytes:output.length,elapsedMs:Date.now()-started,aacPrimingSamples:priming,h264HeapBytes:module.HEAPU8.length,aacHeapBytes:aac.HEAPU8.length,gateA:'PENDING_PLATFORM_DECODE_AND_SEND'}};
 }catch(error){const failure=new Error('WASM proof failed');failure.stage=stage;failure.errorName=error?.name||'Error';throw failure;}
 finally{if(encoder)encoder.delete();if(handle&&aac)aac._ae_destroy(handle);}
}
