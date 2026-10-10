// Local evidence only: execute in V8 without Node globals, then independently decode.
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { createContext, SourceTextModule } from 'node:vm';
import { execFileSync } from 'node:child_process';
const root=resolve(process.argv[2]||'');if(!process.argv[2])throw new Error('Provide the prepared isolated project directory');
const output=resolve(root,'proof.mp4');if(existsSync(output))throw new Error('Refusing to overwrite proof.mp4');
const context=createContext({console:{log(){},error(){},warn(){}},performance:{now:()=>performance.now()}},{codeGeneration:{strings:false,wasm:true}}),cache=new Map();
function load(path){if(cache.has(path))return cache.get(path);const m=new SourceTextModule(readFileSync(path,'utf8'),{context,identifier:path});cache.set(path,m);return m;}
const module=load(resolve(root,'tgcloud/lib/proof/render.js'));
await module.link((specifier,ref)=>{if(!specifier.startsWith('.'))throw new Error('Nonrelative runtime import');return load(resolve(dirname(ref.identifier),specifier));});
await module.evaluate();const result=await module.namespace.renderProof();writeFileSync(output,result.bytes);
const metadata=JSON.parse(execFileSync('ffprobe',['-v','error','-show_streams','-show_format','-of','json',output],{encoding:'utf8'}));
const video=metadata.streams.find(s=>s.codec_type==='video'),audio=metadata.streams.find(s=>s.codec_type==='audio');
if(video?.codec_name!=='h264'||video.width!==640||video.height!==640||video.nb_frames!=='30'||video.r_frame_rate!=='30/1'||audio?.codec_name!=='aac'||audio.sample_rate!=='48000'||audio.channels!==1||Math.abs(Number(metadata.format.duration)-1)>.001)throw new Error('MP4 metadata mismatch');
execFileSync('ffmpeg',['-v','error','-xerror','-i',output,'-f','null','-']);
const frames=execFileSync('ffmpeg',['-v','error','-i',output,'-vf','select=eq(n\\,0)+eq(n\\,15)','-vsync','0','-pix_fmt','rgb24','-f','rawvideo','-'],{maxBuffer:3*640*640*3});
if(frames.length!==2*640*640*3)throw new Error('Unexpected decoded frame count');
const pixel=(f,x,y)=>frames[(f*640*640+y*640+x)*3];
if(pixel(0,500,320)<180||pixel(1,447,447)<180||pixel(1,500,320)>100)throw new Error('Decoded marker did not rotate');
const pcm=execFileSync('ffmpeg',['-v','error','-i',output,'-map','0:a:0','-f','f32le','-'],{maxBuffer:500000});
const samples=new Float32Array(pcm.buffer.slice(pcm.byteOffset,pcm.byteOffset+pcm.byteLength));
if(samples.length<48000||samples.length>49024)throw new Error('Decoded audio duration mismatch');
let energy=0,crossings=0;for(let i=4096;i<45056;i++){energy+=samples[i]**2;if(samples[i-1]<=0&&samples[i]>0)crossings++;}
const rms=Math.sqrt(energy/40960),frequency=crossings*48000/40960;if(rms<.15||rms>.3||Math.abs(frequency-440)>3)throw new Error('Decoded synthetic tone mismatch');
console.log(JSON.stringify({localOnly:true,...result.report,independentDecode:'passed',rotationCheck:'passed',decodedToneHz:frequency,decodedToneRms:rms,output},null,2));
