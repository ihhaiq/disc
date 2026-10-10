// Isolated proof only: add mono AAC-LC to the encoder's genuine AVC MP4.
const bytes=(...parts)=>{const out=new Uint8Array(parts.reduce((n,p)=>n+p.length,0));let i=0;for(const p of parts){out.set(p,i);i+=p.length;}return out;};
const text=s=>Uint8Array.from(s,c=>c.charCodeAt(0));
const u16=n=>Uint8Array.of(n>>>8&255,n&255);
const u32=n=>Uint8Array.of(n>>>24&255,n>>>16&255,n>>>8&255,n&255);
const zeros=n=>new Uint8Array(n);
const box=(name,...parts)=>{const payload=bytes(...parts);return bytes(u32(payload.length+8),text(name),payload);};
const full=(name,flags,...parts)=>box(name,u32(flags),...parts);
function boxes(data){const out=[];let i=0;while(i<data.length){if(i+8>data.length)throw new Error('Truncated MP4 box');const size=new DataView(data.buffer,data.byteOffset+i,4).getUint32(0);if(size<8||i+size>data.length)throw new Error('Unsupported MP4 box size');out.push({type:String.fromCharCode(...data.subarray(i+4,i+8)),start:i,data:data.subarray(i,i+size)});i+=size;}return out;}
function adts(data){const frames=[];let i=0;while(i<data.length){if(i+7>data.length||data[i]!==255||(data[i+1]&246)!==240)throw new Error('Invalid ADTS header');const protection=data[i+1]&1,profile=(data[i+2]>>>6)+1,index=data[i+2]>>>2&15,channels=(data[i+2]&1)<<2|data[i+3]>>>6;const size=(data[i+3]&3)<<11|data[i+4]<<3|data[i+5]>>>5;const header=protection?7:9;if(profile!==2||index!==3||channels!==1||(data[i+6]&3)!==0||size<=header||i+size>data.length)throw new Error('Expected complete mono 48kHz AAC-LC frames');frames.push(data.slice(i+header,i+size));i+=size;}if(!frames.length)throw new Error('No AAC samples');return frames;}
const matrix=bytes(u32(65536),u32(0),u32(0),u32(0),u32(65536),u32(0),u32(0),u32(0),u32(1073741824));
const descriptor=(tag,payload)=>{if(payload.length>=128)throw new Error('Descriptor too large');return bytes(Uint8Array.of(tag,payload.length),payload);};
export function muxProof(video,audio,{priming=2048,sampleCount=48000}={}){
 if(!(video instanceof Uint8Array)||!(audio instanceof Uint8Array)||!Number.isSafeInteger(priming)||priming<0||sampleCount!==48000)throw new Error('Invalid proof input');
 const top=boxes(video),moov=top.find(b=>b.type==='moov');if(!moov||top.filter(b=>b.type==='moov').length!==1)throw new Error('Expected one moov');
 // Removing only trailing metadata preserves all existing video chunk offsets.
 if(top.some(b=>b.start>moov.start&&b.type!=='free'))throw new Error('Expected trailing moov');
 const children=boxes(moov.data.subarray(8)),mvhd=children.find(b=>b.type==='mvhd');if(!mvhd||mvhd.data[8]!==0)throw new Error('Expected v0 mvhd');
 const header=mvhd.data.slice(),view=new DataView(header.buffer);const movieScale=view.getUint32(20);if(!movieScale)throw new Error('Invalid movie timescale');view.setUint32(header.length-4,3);
 const frames=adts(audio),audioDuration=frames.length*1024;if(priming+sampleCount>audioDuration)throw new Error('Insufficient encoded audio');
 const prefix=video.slice(0,moov.start),payload=bytes(...frames),audioOffset=prefix.length+8;
 const esds=full('esds',0,descriptor(3,bytes(u16(2),Uint8Array.of(0),descriptor(4,bytes(Uint8Array.of(64,21),zeros(3),u32(64000),u32(64000),descriptor(5,Uint8Array.of(17,136)))),descriptor(6,Uint8Array.of(2)))));
 const sample=box('mp4a',zeros(6),u16(1),zeros(8),u16(1),u16(16),u16(0),u16(0),u32(48000*65536),esds);
 const stbl=box('stbl',full('stsd',0,u32(1),sample),full('stts',0,u32(1),u32(frames.length),u32(1024)),full('stsc',0,u32(1),u32(1),u32(frames.length),u32(1)),full('stsz',0,u32(0),u32(frames.length),...frames.map(f=>u32(f.length))),full('stco',0,u32(1),u32(audioOffset)));
 const dref=full('dref',0,u32(1),full('url ',1));
 const minf=box('minf',full('smhd',0,u16(0),u16(0)),box('dinf',dref),stbl);
 const mdhd=full('mdhd',0,u32(0),u32(0),u32(48000),u32(audioDuration),u16(21956),u16(0));
 const hdlr=full('hdlr',0,u32(0),text('soun'),zeros(12),text('SoundHandler\0'));
 const mdia=box('mdia',mdhd,hdlr,minf);
 const tkhd=full('tkhd',7,u32(0),u32(0),u32(2),u32(0),u32(movieScale),zeros(8),u16(0),u16(0),u16(256),u16(0),matrix,u32(0),u32(0));
 const edts=box('edts',full('elst',0,u32(1),u32(movieScale),u32(priming),u16(1),u16(0)));
 const trak=box('trak',tkhd,edts,mdia);
 return bytes(prefix,box('mdat',payload),box('moov',...children.map(c=>c.type==='mvhd'?header:c.data),trak));
}
