import { CONFIG, now } from './config.js';
import { api } from 'sdk';
import { getUser, saveSession, getSession, transitionSession, cancelSession,
  sessionForPhoto, sessionKey, canUseColor, limitStatus } from './state.js';
import { tr } from './i18n.js';
import { modeKeyboard, colorKeyboard, speedKeyboard, photoKeyboard, segmentKeyboard, confirmKeyboard, payKeyboard } from './keyboard.js';
import { replyText, editText, answer } from './io.js';
import { STYLES, SPEEDS, rotationSeconds } from './catalog.js';
import { controlsSession } from './context.js';

async function limitMessage(message,uid,lang) {
  const status=await limitStatus(uid);
  if(status.remaining>0)return false;
  await replyText(message,'limited',lang,CONFIG.RENDERER_ENABLED?await payKeyboard(lang):null,{
    limit:status.limit,hours:Math.max(1,Math.ceil(status.resetSeconds/3600)),
    premium_limit:CONFIG.PREMIUM_DAILY_LIMIT,price:CONFIG.STARS_SUBSCRIPTION_PRICE});
  return true;
}

export async function audioReceived(message,kind='private') {
  const audio=message.audio;
  if(!audio?.file_id)return;
  const uid=message.from?.id||0,owner=kind==='channel'?0:uid;
  if(kind==='private'&&!uid)return;
  const user=uid?await getUser(uid):null,lang=user?.lang||'ar';
  if(audio.file_size>CONFIG.MAX_TELEGRAM_AUDIO_SIZE_BYTES) {
    await replyText(message,'size',lang,null,{max_size_mb:CONFIG.MAX_TELEGRAM_AUDIO_SIZE_BYTES/(1024*1024)});return;
  }
  if(kind!=='channel'&&uid&&await limitMessage(message,uid,lang))return;
  const key=sessionKey(message.chat.id,owner,message.message_id,kind);
  const existing=await getSession(key);
  if(existing?.messageId===message.message_id&&existing.audioId===audio.file_id)return;
  const s={key,ownerId:owner,chatId:message.chat.id,messageId:message.message_id,promptId:0,
    audioId:audio.file_id,duration:Math.max(0,audio.duration||0),size:Math.max(0,audio.file_size||0),
    thumbId:audio.thumbnail?.file_id||audio.thumb?.file_id||null,
    style:user?.style||'default',rotation:user?.rotation||'4',step:'mode',mode:'custom',
    revision:message.message_id,offset:0,createdAt:now(),expiresAt:now()+CONFIG.SESSION_TTL_SECONDS};
  if(!await saveSession(s))return;
  try {
    const prompt=await replyText(message,'choose',lang,await modeKeyboard(uid,lang,s));
    if(prompt?.message_id&&!await transitionSession(s,{promptId:prompt.message_id}))
      await api.deleteMessage({chat_id:s.chatId,message_id:prompt.message_id});
  } catch(error) {
    await cancelSession(s);
    throw error;
  }
}

// Claim before contacting Telegram; roll back a failed presentation without undoing a newer transition.
async function change(s,patch,present) {
  if(!await transitionSession(s,patch))return false;
  const next={...s,...patch,revision:(s.revision||0)+1};
  try {
    const prompt=await present(next);
    if(prompt?.message_id&&prompt.message_id!==s.promptId)
      return await transitionSession(next,{promptId:prompt.message_id});
    return true;
  } catch(error) {
    await transitionSession(next,Object.fromEntries(Object.keys(patch).map(key=>[key,s[key]])));
    throw error;
  }
}
export async function advance(s,lang,message=null) {
  if(!s)return false;
  const shared=!s.key.startsWith('u');
  let step,key,markup;
  if(!s.thumbId){
    step='photo';key=shared?'MSG_CHANNEL_ASK_IMAGE_REPLY':'photo';markup=await photoKeyboard(s.ownerId,lang,s);
  }else if(s.duration>CONFIG.MAX_DURATION_SECONDS){
    step='segment';key='segment';markup=await segmentKeyboard(s.ownerId,lang,s);
  }else{
    step='confirm';key='review';markup=await confirmKeyboard(s.ownerId,lang,s);
  }
  return change(s,{step},()=>message?replyText(message,key,lang,markup):
    editText({chat:{id:s.chatId},message_id:s.promptId},key,lang,markup));
}

export async function handlePhoto(message) {
  if(!message.photo?.length)return false;
  const s=await sessionForPhoto(message);
  if(!s||s.step!=='photo')return false;
  const uid=message.from?.id||0;
  if(message.chat.type!=='channel'&&!await controlsSession(uid,s))return false;
  const fileId=message.photo[message.photo.length-1]?.file_id;
  if(!fileId)return false;
  if(!await transitionSession(s,{thumbId:fileId}))return true;
  const current={...s,thumbId:fileId,revision:(s.revision||0)+1},lang=(await getUser(s.ownerId||uid))?.lang||'ar';
  await advance(current,lang,message);
  return true;
}

export async function callbackWizard(c,s,data) {
  const uid=c.from.id,lang=(await getUser(s.ownerId||uid))?.lang||'ar',msg=c.message;
  if(data==='cancel_queue') {
    if(!await cancelSession(s))return false;
    await editText(msg,'MSG_QUEUE_CANCELED_EDIT',lang);
    await answer(c,await tr('MSG_QUEUE_CANCELED_ANSWER',lang));return 'alert';
  }
  if(data==='mode:quick'&&s.step==='mode') {
    if(s.thumbId)return change(s,{mode:'quick',step:'confirm'},async next=>editText(msg,'review',lang,await confirmKeyboard(uid,lang,next)));
    const key=s.key.startsWith('u')?'quickPhoto':'MSG_CHANNEL_ASK_IMAGE_REPLY';
    return change(s,{mode:'quick',step:'photo'},async()=>editText(msg,key,lang,await photoKeyboard(uid,lang,s)));
  }
  if(data==='mode:custom'&&s.step==='mode')
    return change(s,{mode:'custom',step:'color'},async()=>editText(msg,'color',lang,await colorKeyboard(uid,lang,s)));
  if(data.startsWith('wiz_color:')&&s.step==='color') {
    const key=data.slice('wiz_color:'.length);
    if(!STYLES.some(style=>style.key===key))return false;
    if(!await canUseColor(s.ownerId||uid,key)){await answer(c,await tr('premium',lang),true);return 'alert';}
    return change(s,{style:key,step:'speed'},async next=>editText(msg,'speed',lang,await speedKeyboard(lang,next)));
  }
  if(data.startsWith('wiz_speed:')&&s.step==='speed') {
    const speed=data.slice('wiz_speed:'.length);
    if(!SPEEDS.includes(speed))return false;
    const key=s.key.startsWith('u')?'photo':s.thumbId?'MSG_CHANNEL_ASK_IMAGE_REPLY_WITH_SKIP':'MSG_CHANNEL_ASK_IMAGE_REPLY';
    return change(s,{rotation:String(rotationSeconds(speed)),step:'photo'},async next=>editText(msg,key,lang,await photoKeyboard(uid,lang,next)));
  }
  if(data==='wiz_image:skip'&&s.step==='photo') {
    if(!s.thumbId){await answer(c,await tr('noThumb',lang),true);return 'alert';}
    return advance(s,lang);
  }
  if(data.startsWith('wiz_segment_page:')&&s.step==='segment') {
    const raw=data.slice('wiz_segment_page:'.length),page=Number(raw),total=Math.ceil(Math.max(1,Math.ceil(s.duration/60))/20);
    if(!/^\d+$/.test(raw)||!Number.isSafeInteger(page)||page<0||page>=total)return false;
    await editText(msg,'segment',lang,await segmentKeyboard(uid,lang,s,page));return true;
  }
  if(data.startsWith('wiz_segment:')&&s.step==='segment') {
    const raw=data.slice('wiz_segment:'.length),offset=Number(raw);
    if(!/^\d+$/.test(raw)||!Number.isSafeInteger(offset)||offset<0||offset>=s.duration||offset%60!==0)return false;
    return change(s,{offset,step:'confirm'},async next=>editText(msg,'review',lang,await confirmKeyboard(uid,lang,next)));
  }
  if(['wiz_preview_confirm','wiz_full_confirm'].includes(data)&&s.step==='confirm') {
    // Gate A has not passed: preserve the request, never pretend to render or charge usage.
    await answer(c,await tr('renderer',lang),true);return 'alert';
  }
  return false;
}
