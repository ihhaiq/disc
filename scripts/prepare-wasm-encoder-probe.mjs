// Downloads integrity-pinned build inputs; creates an isolated, unlinked CLI project.
import { mkdirSync, readFileSync, writeFileSync, mkdtempSync, rmSync, copyFileSync, existsSync } from 'node:fs';
import { resolve, join, isAbsolute } from 'node:path';
import { tmpdir } from 'node:os';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
const target=resolve(process.argv[2]||'');
if(!process.argv[2]||!isAbsolute(process.argv[2])||existsSync(target))throw new Error('Provide a NEW absolute directory for the isolated WASM encoder probe');
if(!process.env.npm_execpath)throw new Error('Run through npm run prepare:wasm-probe');
const scratch=mkdtempSync(join(tmpdir(),'disc-wasm-build-'));
const inputs=[
 {name:'h264-mp4-encoder@1.0.12',hash:'xih3J+Go0o1RqGjhOt6TwXLWWGqLONRPyS8yoMu/RoS/S8WyEv4HuHp1KBsDDl8srZQ3gw9f95JYkCSjCuZbHQ=='},
 {name:'@audio/encode-aac@1.2.1',hash:'VUAyqoPpiYkk8CZ7sCxwO4jIqgWEGrm67ue9UcXOI8XaIR3n1edFk8gJTeJoT/JwPUxtJ8mShIVZWy2VW+UZeA=='}
];
let created=false;
const replace=(s,from,to)=>{if(!s.includes(from))throw new Error('Pinned source shape changed');return s.replace(from,to);};
try{
 const dirs=[],archives=[];
 for(const [i,input] of inputs.entries()){
  const packed=JSON.parse(execFileSync(process.execPath,[process.env.npm_execpath,'pack',input.name,'--json','--ignore-scripts','--pack-destination',scratch,'--cache',join(scratch,'npm-cache')],{encoding:'utf8'}));
  const archive=join(scratch,packed[0].filename);archives.push(archive);
  if(createHash('sha512').update(readFileSync(archive)).digest('base64')!==input.hash)throw new Error('Package integrity mismatch');
  const dir=join(scratch,String(i));mkdirSync(dir);execFileSync('tar',['-xzf',archive,'-C',dir]);dirs.push(join(dir,'package'));
 }
 const map=JSON.parse(readFileSync(join(dirs[0],'embuild/dist/h264-mp4-encoder.web.js.map'),'utf8'));
 const index=map.sources.findIndex(s=>s.endsWith('/embuild/h264-mp4-encoder.js'));if(index<0)throw new Error('Missing H264 source');
 let h264=map.sourcesContent[index];
 const envStart=h264.indexOf('var ba='),envEnd=h264.indexOf('var oa=');if(envStart<0||envEnd<=envStart)throw new Error('Missing H264 environment adapter');
 h264=h264.slice(0,envStart)+'var ba="probe",ca=false,v=false,da=false,ea=true,y="",fa,ha,ia,ja;'+h264.slice(envEnd);
 h264=replace(h264,'var L,M;','e.instantiateWasm=function(imports,receive){var compiled=new WebAssembly.Module(eb());var instance=new WebAssembly.Instance(compiled,imports);receive(instance);return instance.exports;};var L,M;');
 h264=replace(h264,"function Nb(a,b){a=Mb(a);return(new Function(\"body\",\"return function \"+a+'() {\\n    \"use strict\";    return body.apply(this, arguments);\\n};\\n'))(b)}","function Nb(a,b){const fn=function(){return b.apply(this,arguments);};Object.defineProperty(fn,'name',{value:Mb(a)});return fn;} ");
 h264=replace(h264,"c=(new Function(\"dynCall\",\"rawFunction\",f+\"};\\n\"))(c,b);","c=(function(call,raw){const fn=function(...args){return call(raw,...args);};Object.defineProperty(fn,'length',{value:a.length-1});return fn;})(c,b);");
 h264=replace(h264,'else if(da)try{var c=require("crypto");b=function(){return c.randomBytes(1)[0]}}catch(d){}','');
 h264=replace(h264,"var w=t,x=n,D=g,F=r.length;2>F&&T(\"argTypes array size mismatch! Must at least get return value and 'this' types!\");var E=null!==r[1]&&null!==x,la=!1;for(x=1;x<r.length;++x)if(null!==r[x]&&void 0===r[x].O){la=!0;break}var tc=\"void\"!==r[0].name,ma=\"\",za=\"\";for(x=0;x<F-2;++x)ma+=(0!==x?\", \":\"\")+\"arg\"+x,za+=(0!==x?\", \":\"\")+\"arg\"+x+\"Wired\";w=\"return function \"+Mb(w)+\"(\"+ma+\") {\\nif (arguments.length !== \"+\n(F-2)+\") {\\nthrowBindingError('function \"+w+\" called with ' + arguments.length + ' arguments, expected \"+(F-2)+\" args!');\\n}\\n\";la&&(w+=\"var destructors = [];\\n\");var uc=la?\"destructors\":\"null\";ma=\"throwBindingError invoker fn runDestructors retType classParam\".split(\" \");D=[T,D,k,Bc,r[0],r[1]];E&&(w+=\"var thisWired = classParam.toWireType(\"+uc+\", this);\\n\");for(x=0;x<F-2;++x)w+=\"var arg\"+x+\"Wired = argType\"+x+\".toWireType(\"+uc+\", arg\"+x+\"); // \"+r[x+2].name+\"\\n\",ma.push(\"argType\"+x),D.push(r[x+2]);\nE&&(za=\"thisWired\"+(0<za.length?\", \":\"\")+za);w+=(tc?\"var rv = \":\"\")+\"invoker(fn\"+(0<za.length?\", \":\"\")+za+\");\\n\";if(la)w+=\"runDestructors(destructors);\\n\";else for(x=E?1:2;x<r.length;++x)F=1===x?\"thisWired\":\"arg\"+(x-2)+\"Wired\",null!==r[x].O&&(w+=F+\"_dtor(\"+F+\"); // \"+r[x].name+\"\\n\",ma.push(F+\"_dtor\"),D.push(r[x].O));tc&&(w+=\"var ret = retType.fromWireType(rv);\\nreturn ret;\\n\");ma.push(w+\"}\\n\");r=Cc(ma).apply(null,D);","const types=r,hasThis=types[1]!==null&&n!==null,needsList=types.slice(1).some(type=>type!==null&&type.O===undefined);r=function(...args){if(args.length!==types.length-2)T(\"Binding argument count mismatch\");const destructors=needsList?[]:null,wired=[],wireTypes=[];if(hasThis){wired.push(types[1].toWireType(destructors,this));wireTypes.push(types[1]);}for(let index=0;index<args.length;index++){wired.push(types[index+2].toWireType(destructors,args[index]));wireTypes.push(types[index+2]);}const value=g(k,...wired);if(needsList)Bc(destructors);else wireTypes.forEach((type,index)=>{if(type.O!==null)type.O(wired[index]);});return types[0].name===\"void\"?undefined:types[0].fromWireType(value);};Object.defineProperty(r,\"length\",{value:types.length-2});Object.defineProperty(r,\"name\",{value:Mb(t)});");
 const exportStart=h264.indexOf("if (typeof exports === 'object'");if(exportStart<0)throw new Error('Missing H264 export adapter');
 h264=h264.slice(0,exportStart)+'\nexport default H264MP4Module;\n';
 let aac=readFileSync(join(dirs[1],'src/fdk.wasm.js'),'utf8');const aacStart=aac.indexOf('var ENVIRONMENT_IS_AUDIO_WORKLET'),aacEnd=aac.indexOf('var out=');
 if(aacStart<0||aacEnd<=aacStart)throw new Error('Missing AAC environment adapter');
 aac=aac.slice(0,aacStart)+'var ENVIRONMENT_IS_AUDIO_WORKLET=false,ENVIRONMENT_IS_WEB=false,ENVIRONMENT_IS_WORKER=false,ENVIRONMENT_IS_NODE=false,ENVIRONMENT_IS_SHELL=false;var arguments_=[],thisProgram="probe",quit_=(status,error)=>{throw error},scriptDirectory="",readAsync,readBinary;'+aac.slice(aacEnd);
 const wasmStart=aac.indexOf('async function createWasm(){'),wasmEnd=aac.indexOf('class ExitStatus');if(wasmStart<0||wasmEnd<=wasmStart)throw new Error('Missing AAC loader adapter');
 aac=aac.slice(0,wasmStart)+'function createWasm(){var compiled=new WebAssembly.Module(findWasmBinary());var instance=new WebAssembly.Instance(compiled,getWasmImports());wasmExports=instance.exports;assignWasmExports(wasmExports);updateMemoryViews();return wasmExports;}'+aac.slice(wasmEnd);
 aac=replace(aac,'wasmExports=await (createWasm());','wasmExports=createWasm();');
 mkdirSync(target);created=true;
 mkdirSync(join(target,'tgcloud/lib/proof'),{recursive:true});mkdirSync(join(target,'tgcloud/handlers'));
 writeFileSync(join(target,'tgcloud/lib/proof/h264-core.js'),h264);
 writeFileSync(join(target,'tgcloud/lib/proof/aac-core.js'),aac);
 for(const name of ['mux.js','render.js'])copyFileSync(fileURLToPath(new URL('./templates/wasm-probe/'+name,import.meta.url)),join(target,'tgcloud/lib/proof',name));
 writeFileSync(join(target,'tgcloud/handlers/message.js'),`import { api, InputFile } from 'sdk';\nimport { renderProof } from '../lib/proof/render.js';\nexport default async function (args) {\n try {\n  if(args?.send===true && (!Number.isSafeInteger(args.chatId)||args.chatId===0))return {stage:'invalid-chat'};\n  const result=await renderProof();\n  if(args?.send===true){await api.sendVideoNote({chat_id:args.chatId,video_note:new InputFile(result.bytes,'wasm-proof.mp4',{type:'video/mp4'}),duration:1,length:640});result.report.sent=true;}\n  return result.report;\n }catch(error){return {stage:error.stage||'send',errorName:error.errorName||error.name,gateA:'BLOCKED'};}\n}\n`);
 writeFileSync(join(target,'package.json'),JSON.stringify({name:'disc-wasm-encoder-probe',private:true,type:'module',devDependencies:{'@tgcloud/cli':'0.2.0'}},null,2)+'\n');
 writeFileSync(join(target,'tgcloud.jsonc'),'{"static":false}\n');writeFileSync(join(target,'.gitignore'),'.tgcloud/\nnode_modules/\nproof.mp4\n');
 mkdirSync(join(target,'licenses'));
 copyFileSync(fileURLToPath(new URL('./templates/wasm-probe/MPL-1.1.txt',import.meta.url)),join(target,'licenses/MPL-1.1.txt'));
 mkdirSync(join(target,'upstream-sources'));archives.forEach((archive,i)=>copyFileSync(archive,join(target,'upstream-sources',i+'.tgz')));
 writeFileSync(join(target,'licenses/SOURCES.md'),'h264-mp4-encoder 1.0.12: MIT wrapper, public-domain minih264, MPL-1.1 libmp4v2. Upstream sources: https://github.com/TrevorSundberg/h264-mp4-encoder , https://github.com/TrevorSundberg/minih264 , https://github.com/TrevorSundberg/libmp4v2 . @audio/encode-aac 1.2.1: MIT wrapper and FDK-AAC license/patent terms. Exact integrity-verified original packages retained in upstream-sources/. Modified loaders generated by scripts/prepare-wasm-encoder-probe.mjs. Codec binary bytes are unchanged.\n');copyFileSync(join(dirs[0],'LICENSE.md'),join(target,'licenses/h264-mp4-encoder.txt'));
 copyFileSync(join(dirs[1],'LICENSE'),join(target,'licenses/audio-encode-aac.txt'));copyFileSync(join(dirs[1],'LICENSE.fdk-aac'),join(target,'licenses/FDK-AAC.txt'));
 writeFileSync(join(target,'README.md'),'# Isolated encoder feasibility candidate\n\nNOT the production renderer. Synthetic rotating marker + 440Hz tone, 640x640/30fps/1s. Integrity-pinned MIT minih264 wrapper and MIT/FDK-AAC inputs; keep licenses. AAC redistribution has upstream FDK license/patent terms. No real user audio, original vinyl assets or production integration.\n\n`npm install --ignore-scripts`, then link a TEST bot with `npx tgcloud login`. `npx tgcloud run handlers/message "{}"` encodes without sending. Do not push or migrate this project. Sending is opt-in with a nonzero numeric chatId and send:true; account must be the chosen test bot and recipient must have started it. Platform module sizes, memory/CPU and codec compatibility remain unverified until the actual run. An encoded report is not Gate A: independently decode and verify the actual delivered file.\n');
 console.log('Prepared isolated WASM encoder candidate:',target);
}catch(error){if(created)rmSync(target,{recursive:true,force:true});throw error;}finally{rmSync(scratch,{recursive:true,force:true});}
