import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const source=readFileSync(new URL('../../tgcloud/lib/wizard.js',import.meta.url),'utf8')
 .replace(/^import\s+[\s\S]*?\s+from\s+['"][^'"]+['"];\s*$/gm,'')
 .replace(/\bexport\s+(?=const|function|async|class)/g,'');
function harness({channel=false}={}){
 const calls=[],session={
  key:channel?'c-100:11':'u9',ownerId:channel?0:9,chatId:channel?-100:9,
  messageId:11,promptId:50,style:'default',rotation:'4',duration:30,thumbId:null,
  step:channel?'photo':'color',createdAt:1,expiresAt:9999999999
 };
 const db={select:()=>({from:()=>({where:()=>({orderBy:()=>({limit:()=>({get:async()=>channel?session:null})})})})})};
 const vars={
  api:{deleteMessage:async()=>calls.push(['deleteMessage'])}, db,
  eq:(...args)=>args,and:(...args)=>args,desc:x=>x,
  sessions:{ownerId:'ownerId',chatId:'chatId',step:'step',promptId:'promptId',createdAt:'createdAt'},
  CONFIG:{MAX_DURATION_SECONDS:60,RENDERER_ENABLED:false},
  now:()=>1000,getUser:async()=>({lang:'ar'}),
  saveSession:async()=>{},getSession:async key=>key===session.key?session:null,
  patchSession:async(key,patch)=>{assert.equal(key,session.key);Object.assign(session,patch);calls.push(['patch',patch]);},
  deleteSession:async key=>calls.push(['delete',key]),sessionKey:()=>session.key,
  canUseColor:async()=>true,limitStatus:async()=>({remaining:3}),
  tr:async key=>key,modeKeyboard:async()=>({}),colorKeyboard:async()=>({}),
  speedKeyboard:async()=>({}),photoKeyboard:async()=>({}),segmentKeyboard:async()=>({}),
  confirmKeyboard:async()=>({}),reply:async()=>({message_id:55}),
  edit:async(m,text)=>calls.push(['edit',text]),
  answer:async(c,text)=>calls.push(['answer',text]),
  send:async()=>({message_id:56}),styleOf:key=>({key}),
  SPEEDS:['full','8','19','33','45'],rotationSeconds:s=>60/Number(s)
 };
 const api=new Function(...Object.keys(vars),source+';return {callbackWizard,handlePhoto};')(...Object.values(vars));
 return {calls,session,...api};
}
test('custom wizard transitions choose color -> speed -> image',async()=>{
 const h=harness(),c={id:'1',from:{id:9},message:{chat:{id:9},message_id:50}};
 assert.equal(await h.callbackWizard(c,h.session,'wiz_color:blue'),true);
 assert.equal(h.session.style,'blue');
 assert.equal(h.session.step,'speed');
 assert.equal(await h.callbackWizard(c,h.session,'wiz_speed:33'),true);
 assert.equal(h.session.step,'photo');
 assert.ok(Math.abs(Number(h.session.rotation)-(60/33))<1e-10);
});
test('cancel leaves no active session, uses main messages once',async()=>{
 const h=harness(),c={id:'1',from:{id:9},message:{chat:{id:9},message_id:50}};
 assert.equal(await h.callbackWizard(c,h.session,'cancel_queue'),'alert');
 assert.equal(h.calls.filter(e=>e[0]==='delete').length,1);
 assert.ok(h.calls.some(e=>e[1]==='MSG_QUEUE_CANCELED_EDIT'));
 assert.ok(h.calls.some(e=>e[1]==='MSG_QUEUE_CANCELED_ANSWER'));
});
test('channel cover-photo reply selects matching pending prompt and advances',async()=>{
 const h=harness({channel:true});
 const ok=await h.handlePhoto({chat:{id:-100,type:'channel'},
  photo:[{file_id:'PHOTO'}],reply_to_message:{message_id:50}});
 assert.equal(ok,true);
 assert.equal(h.session.thumbId,'PHOTO');
 assert.equal(h.session.step,'confirm');
 assert.equal(h.session.promptId,55);
});
