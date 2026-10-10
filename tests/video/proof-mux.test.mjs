import test from 'node:test';
import assert from 'node:assert/strict';
import { muxProof } from '../../scripts/templates/wasm-probe/mux.js';
const box=(type,payload=new Uint8Array())=>{const bytes=new Uint8Array(payload.length+8);new DataView(bytes.buffer).setUint32(0,bytes.length);bytes.set(Uint8Array.from(type,c=>c.charCodeAt(0)),4);bytes.set(payload,8);return bytes;};
const movie=()=>{const mvhd=new Uint8Array(100);new DataView(mvhd.buffer).setUint32(12,1000);return box('moov',box('mvhd',mvhd));};
test('proof mux rejects corrupt/truncated or unsupported MP4 boxes',()=>{
 for(const video of [new Uint8Array(),Uint8Array.of(0,0,0),Uint8Array.of(0,0,0,100,109,111,111,118),box('mdat')])assert.throws(()=>muxProof(video,new Uint8Array()));
});
test('proof mux refuses media after moov rather than silently corrupting video offsets',()=>{
 const moov=movie(),media=box('mdat'),video=new Uint8Array(moov.length+media.length);video.set(moov);video.set(media,moov.length);
 assert.throws(()=>muxProof(video,Uint8Array.of(255,241,76,64,0,31,252)),/trailing moov/);
});
test('proof mux rejects missing, truncated and incompatible AAC input',()=>{
 const video=movie();
 for(const audio of [new Uint8Array(),Uint8Array.of(255,241),Uint8Array.of(255,241,80,64,0,31,252),Uint8Array.of(255,241,76,64,2,31,252)])assert.throws(()=>muxProof(video,audio),/AAC|ADTS/);
 assert.throws(()=>muxProof(video,new Uint8Array(),{priming:-1}),/input/);
});
