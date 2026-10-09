import { api } from 'sdk';
import { tr, textValue } from './i18n.js';
import { escapeHtml, normalizeRichMedia, richTextFallback } from './dev-text-utils.js';

export function parseFailure(error) {
  return /can't parse entities|can't find end tag|unsupported start tag|entity parsing/i
    .test(String(error?.description||''));
}
function richUnsupported(error) {
  return error?.code===400&&/rich|not supported|unknown method|method not found/i.test(error.description||'')||error?.code===404;
}
export function plainText(text) {
  return String(text??'').replace(/<[^>]*>/g,'').replace(/&lt;/g,'<')
    .replace(/&gt;/g,'>').replace(/&quot;/g,'"').replace(/&#39;/g,"'").replace(/&amp;/g,'&');
}
async function htmlCall(method,props) {
  try {return await api[method](props);}
  catch(error) {
    if(/message is not modified/i.test(error?.description||''))return null;
    if(!parseFailure(error))throw error;
    const next={...props,parse_mode:undefined};
    if(next.text!=null)next.text=plainText(next.text);
    if(next.caption!=null)next.caption=plainText(next.caption);
    return api[method](next);
  }
}
export async function reply(message,text,reply_markup=null) {
  return htmlCall('sendMessage',{chat_id:message.chat.id,text,parse_mode:'HTML',
    reply_parameters:{message_id:message.message_id,allow_sending_without_reply:true},
    ...(reply_markup?{reply_markup}:{})});
}
export async function send(chatId,text,markup=null) {
  return htmlCall('sendMessage',{chat_id:chatId,text,parse_mode:'HTML',...(markup?{reply_markup:markup}:{})});
}
export async function edit(message,text,markup=null) {
  const base={chat_id:message.chat.id,message_id:message.message_id,parse_mode:'HTML',reply_markup:markup||{inline_keyboard:[]}};
  return message.photo?.length ? htmlCall('editMessageCaption',{...base,caption:text}) : htmlCall('editMessageText',{...base,text});
}
export async function deliverRich(message,rich,text,markup=null,{editing=false,replying=true}={}) {
  const content=rich?.blocks?.length?{blocks:normalizeRichMedia(rich.blocks)}:{html:rich?.html||text};
  if(typeof rich?.is_rtl==='boolean')content.is_rtl=rich.is_rtl;
  const props={chat_id:message.chat.id,rich_message:content,
    ...(editing?{message_id:message.message_id,reply_markup:markup||{inline_keyboard:[]}}:
      {...(replying?{reply_parameters:{message_id:message.message_id,allow_sending_without_reply:true}}:{}),...(markup?{reply_markup:markup}:{})})};
  try {return await api[editing?'editMessageText':'sendRichMessage'](props);}
  catch(error) {
    if(/message is not modified/i.test(error?.description||''))return null;
    if(!parseFailure(error)&&!richUnsupported(error))throw error;
    const fallback=text||escapeHtml(richTextFallback(rich?.blocks));
    return editing?edit(message,fallback,markup):replying?reply(message,fallback,markup):send(message.chat.id,fallback,markup);
  }
}
export async function replyText(message,key,lang='ar',markup=null,params={}) {
  const value=await textValue(key,lang,params);
  return value.rich?deliverRich(message,value.rich,value.text,markup):reply(message,value.text,markup);
}
export async function editText(message,key,lang='ar',markup=null,params={}) {
  const value=await textValue(key,lang,params);
  return value.rich?deliverRich(message,value.rich,value.text,markup,{editing:true}):edit(message,value.text,markup);
}
export async function sendText(chatId,key,lang='ar',markup=null,params={}) {
  const value=await textValue(key,lang,params);
  return value.rich?deliverRich({chat:{id:chatId}},value.rich,value.text,markup,{replying:false}):send(chatId,value.text,markup);
}
export async function answer(callback,text='',alert=false) {
  return api.answerCallbackQuery({callback_query_id:callback.id,...(text?{text:plainText(text).slice(0,200),show_alert:alert}:{})});
}
export async function textFor(uid,lang,key,params={}) {return tr(key,lang,params);}
