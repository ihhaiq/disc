// Durable wizard transitions, no long-running jobs in isolates.
import { CONFIG, now } from './config.js';
import { db } from 'sdk';
import { eq, and, desc } from 'sdk/db';
import { sessions } from '../schema.js';
import { getUser, saveSession, getSession, patchSession, deleteSession, sessionKey, canUseColor, limitStatus } from './state.js';
import { tr } from './i18n.js';
import { modeKeyboard, colorKeyboard, speedKeyboard, photoKeyboard, segmentKeyboard, confirmKeyboard } from './keyboard.js';
import { reply, edit, answer, send } from './io.js';
import { styleOf, SPEEDS, rotationSeconds } from './catalog.js';

export async function audioReceived(message,kind='private') {
  const audio=message.audio;
  if(!audio)return;
  const uid=message.from?.id || message.from_user?.id || 0;
  const lang=(await getUser(uid))?.lang || 'ar';
  if(audio.file_size > CONFIG.MAX_TELEGRAM_AUDIO_SIZE_BYTES) {
    await reply(message,await tr('size',lang));return;
  }
  const owner=kind==='channel'?0:uid;
  const key=sessionKey(message.chat.id,owner,message.message_id,kind);
  const user=uid?await getUser(uid):null;
  const s={
    key,ownerId:owner,chatId:message.chat.id,messageId:message.message_id,promptId:0,
    audioId:audio.file_id,duration:audio.duration || 0,size:audio.file_size||0,
    thumbId:audio.thumbnail?.file_id || audio.thumb?.file_id || null,
    style:user?.style||'default',rotation:user?.rotation||'4',
    step:'mode',offset:0,createdAt:now(),expiresAt:now()+CONFIG.SESSION_TTL_SECONDS
  };
  await saveSession(s);
  const prompt=await reply(message,await tr('choose',lang),await modeKeyboard(uid,lang,s));
  if(prompt?.message_id) await patchSession(key,{promptId:prompt.message_id});
}
export async function handlePhoto(message) {
  if(!message.photo?.length)return false;
  const uid=message.from?.id || message.from_user?.id || 0;
  if(!uid)return false;
  // One personal context or the latest active group session from the same sender.
  let s=await getSession('u'+uid);
  if(!s && message.reply_to_message?.message_id) {
    s=await getSession('g'+message.chat.id+':'+message.reply_to_message.message_id);
  }
  if(!s && message.reply_to_message?.message_id && ['group','supergroup'].includes(message.chat.type)) {
    const recent=await db.select().from(sessions).where(and(eq(sessions.ownerId,uid),eq(sessions.chatId,message.chat.id),eq(sessions.step,'photo'),eq(sessions.promptId,message.reply_to_message?.message_id||0)))
      .orderBy(desc(sessions.createdAt)).limit(1).get();
    if(recent) s=await getSession(recent.key);
  }
  if(!s || s.step!=='photo')return false;
  const lang=(await getUser(uid))?.lang||'ar';
  await patchSession(s.key,{thumbId:message.photo[message.photo.length-1].file_id});
  await advance(await getSession(s.key),lang,message);
  return true;
}
export async function advance(s,lang,message=null) {
  if(!s)return;
  let markup,text,step;
  if(!s.thumbId) {
    text=await tr('photo',lang);markup=await photoKeyboard(s.ownerId,lang,s);step='photo';
  }else if(s.duration>CONFIG.MAX_DURATION_SECONDS) {
    text=await tr('segment',lang);markup=await segmentKeyboard(s.ownerId,lang,s);step='segment';
  }else {
    text=await tr('review',lang);markup=await confirmKeyboard(s.ownerId,lang,s);step='confirm';
  }
  await patchSession(s.key,{step});
  const prompt=message?await reply(message,text,markup):await send(s.chatId,text,markup);
  if(prompt?.message_id)await patchSession(s.key,{promptId:prompt.message_id});
}
export async function callbackWizard(c,s,data) {
  const uid=c.from.id,lang=(await getUser(uid))?.lang||'ar', chatMsg=c.message;
  if(data==='cancel_queue'){await deleteSession(s.key);await edit(chatMsg,await tr('expired',lang));return true;}
  if(data==='mode:quick'){
    if(!s.thumbId){await patchSession(s.key,{step:'photo'});await edit(chatMsg,await tr('quickPhoto',lang),await photoKeyboard(uid,lang,s));return true;}
    await advance(s,lang);return true;
  }
  if(data==='mode:custom'){
    await patchSession(s.key,{step:'color'});
    await edit(chatMsg,await tr('color',lang),await colorKeyboard(uid,lang,s));return true;
  }
  if(data.startsWith('wiz_color:')&&s.step==='color'){
    const key=data.split(':')[1],valid=styleOf(key).key===key;
    if(!valid)return true;
    if(!(await canUseColor(uid,key))){await answer(c,await tr(CONFIG.RENDERER_ENABLED?'premium':'renderer',lang),true);return 'alert';}
    await patchSession(s.key,{style:key,step:'speed'});
    await edit(chatMsg,await tr('speed',lang),await speedKeyboard(lang,{...s,style:key}));return true;
  }
  if(data.startsWith('wiz_speed:')&&s.step==='speed'){
    const speed=data.split(':')[1];if(!SPEEDS.includes(speed))return true;
    const value=rotationSeconds(speed);
    await patchSession(s.key,{rotation:String(value),step:'photo'});
    await edit(chatMsg,await tr('photo',lang),await photoKeyboard(uid,lang,s));return true;
  }
  if(data==='wiz_image:skip'&&s.step==='photo'){
    if(!s.thumbId){await answer(c,await tr('noThumb',lang),true);return 'alert';}
    await advance(s,lang);return true;
  }
  if(data.startsWith('wiz_segment_page:')&&s.step==='segment'){
    const page=Number(data.slice('wiz_segment_page:'.length));
    const total=Math.ceil(Math.max(1,Math.ceil(s.duration/60))/20);
    if(!Number.isSafeInteger(page)||page<0||page>=total)return true;
    await edit(chatMsg,await tr('segment',lang),await segmentKeyboard(uid,lang,s,page));
    return true;
  }
  if(data.startsWith('wiz_segment:')&&s.step==='segment'){
    const offset=Number(data.split(':')[1]);
    if(!Number.isInteger(offset)||offset<0||offset>=s.duration||offset%60!==0)return true;
    await patchSession(s.key,{offset,step:'confirm'});
    await edit(chatMsg,await tr('review',lang),await confirmKeyboard(uid,lang,s));return true;
  }
  if(['wiz_preview_confirm','wiz_full_confirm'].includes(data)&&s.step==='confirm') {
    // No render or usage charge until a real FFmpeg-equivalent backend exists.
    await answer(c,await tr('renderer',lang),true);return 'alert';
  }
  return false;
}
