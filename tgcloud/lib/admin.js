import { api, db } from 'sdk';
import { eq } from 'sdk/db';
import { whitelist, premiumColors, overrides } from '../schema.js';
import { developer, now } from './config.js';
import { STYLES } from './catalog.js';
import { developerKeyboard, kb } from './keyboard.js';
import { tr } from './i18n.js';
import { updateUser } from './state.js';
import { reply, edit, answer } from './io.js';
import { ORIGINAL_AR, ORIGINAL_EN } from './original-texts.js';
import { escapeHtml, extractMessageContent, normalizeDevText, emojiSyntaxError, normalizeRichMedia } from './dev-text-utils.js';

const btn=(text,callback_data)=>({text,callback_data});
export async function devStart(message) {
  if(message.chat.type!=='private'||!developer(message.from?.id)) return false;
  await updateUser(message.from.id,{pendingAction:''});
  await reply(message,(await tr('MSG_DEV_CHOOSE_TEMPLATE','ar'))+
    '\n\n🔍 <code>/search كلمة</code> — للبحث بأسماء المتغيرات ومحتواها'+
    '\n✏️ <code>/edit VAR_NAME [ar|en]</code> — لتحرير متغيّر مباشرة بالاسم',
    await developerKeyboard());
  return true;
}
const TEXTS_PER_PAGE=5;
const choices=lang=>Object.entries(lang==='en'?ORIGINAL_EN:ORIGINAL_AR)
  .filter(([k,v])=>!k.startsWith('__')&&typeof v==='string')
  .map(([k])=>k).sort((a,b)=>a.localeCompare(b));
async function textPage(chatMessage,lang,requested) {
  const keys=choices(lang),last=Math.max(0,Math.ceil(keys.length/TEXTS_PER_PAGE)-1);
  const page=Math.max(0,Math.min(last,requested));
  const subset=keys.slice(page*TEXTS_PER_PAGE,(page+1)*TEXTS_PER_PAGE);
  const rows=subset.map(key=>[btn(key,'dev_text:edit:'+lang+':'+key)]);
  const nav=[];
  if(page>0)nav.push(btn('⬅️ السابق','dev_text:page:'+lang+':'+(page-1)));
  if(page<last)nav.push(btn('التالي ➡️','dev_text:page:'+lang+':'+(page+1)));
  if(nav.length)rows.push(nav);
  rows.push([btn(lang==='en'?'🇮🇶 عربي':'🇬🇧 English','dev_text:page:'+(lang==='en'?'ar':'en')+':0')]);
  rows.push([btn('🔙 رجوع','dev_text:back')]);
  await edit(chatMessage,'✏️ تحرير النصوص ('+(lang==='en'?'English':'عربي')+
    ') — صفحة '+(page+1)+'/'+(last+1)+' ('+keys.length+' متغيّر):',kb(rows));
}
async function editPrompt(message,uid,key,lang){
  const dict=lang==='en'?ORIGINAL_EN:ORIGINAL_AR;
  if(!Object.hasOwn(dict,key)||typeof dict[key]!=='string')return false;
  const dbKey=lang==='en'?'EN::'+key:key;
  const edited=await db.select().from(overrides).where(eq(overrides.key,dbKey)).get();
  const value=String(edited?.value??dict[key]);
  await updateUser(uid,{pendingAction:'edit:'+dbKey});
  await reply(message,'📝 القيمة الحالية لـ <code>'+escapeHtml(key)+'</code> ('+
    (lang==='en'?'English':'عربي')+'):\n\n<code>'+escapeHtml(value.slice(0,500))+
    (value.length>500?'…':'')+'</code>\n\nأرسل النص أو رسالة Rich جديدة. للإلغاء: /cancel_edit');
  return true;
}
async function whitelistView(chatMessage,requested=0){
  const rows=await db.select().from(whitelist).all();
  const names=rows.map(x=>x.id).sort((a,b)=>a-b),last=Math.max(0,Math.ceil(names.length/20)-1),page=Math.min(last,requested);
  const shown=names.slice(page*20,(page+1)*20),nav=[];
  if(page>0)nav.push(btn('⬅️ السابق','dev_whitelist:page:'+(page-1)));
  if(page<last)nav.push(btn('التالي ➡️','dev_whitelist:page:'+(page+1)));
  const markup=kb([...shown.map(id=>[btn('❌ إزالة '+id,'dev_whitelist:remove:'+id)]),...(nav.length?[nav]:[]),
    [btn('➕ إضافة مستخدم','dev_whitelist:add')],[btn(await tr('BTN_BACK','ar'),'dev_whitelist:back')]]);
  await edit(chatMessage,'🛡️ القائمة البيضاء (مستثناة من كل الحدود اليومية):\n\n'+
    (names.length?shown.map(id=>'• '+id).join('\n'):'لا يوجد أحد حاليًا.')+'\nصفحة '+(page+1)+'/'+(last+1),markup);
}
async function colorView(chatMessage){
  const rows=[];
  for(const s of STYLES){
    const entry=await db.select().from(premiumColors).where(eq(premiumColors.key,s.key)).get();
    const paid=Boolean(entry?.paid),revision=entry?.revision||0;
    rows.push([btn((await tr(s.textKey,'ar'))+' — '+
      (await tr(paid?'BTN_DEV_LIMITS_PAID_SUFFIX':'BTN_DEV_LIMITS_FREE_SUFFIX','ar')),
      'dev_limits:set:'+s.key+':r'+revision+':'+(paid?0:1))]);
  }
  rows.push([btn(await tr('BTN_BACK','ar'),'dev_limits:back')]);
  await edit(chatMessage,await tr('MSG_DEV_LIMITS_HEADER','ar'),kb(rows));
}
export async function developerCallback(c,data){
  const uid=c.from.id;
  if(c.message.chat.type!=='private'||!developer(uid)){await answer(c,await tr('MSG_DEV_ONLY_OPTION','ar'),true);return 'answered';}
  if(data==='dev_limits:open'||data.startsWith('dev_limits:set:')||data.startsWith('dev_limits:toggle:')){
    if(data!=='dev_limits:open'){
      const match=data.match(/^dev_limits:set:([a-z]+):r(\d{1,12}):([01])$/);
      if(!match||!STYLES.some(x=>x.key===match[1])){
        await colorView(c.message);await answer(c,'القائمة قديمة أو الخيار غير صحيح؛ استخدم الأزرار المحدّثة.',true);return 'answered';
      }
      const [,key,rawRevision,rawPaid]=match,revision=Number(rawRevision),paid=Number(rawPaid);
      // A button names a desired state and the revision it observed. Replays cannot toggle it back.
      const result=await db.run('INSERT INTO vinyl_paid_colors (key,paid,revision) SELECT :key,:paid,1 WHERE :revision = 0 OR EXISTS (SELECT 1 FROM vinyl_paid_colors WHERE key = :key) ON CONFLICT(key) DO UPDATE SET paid = excluded.paid, revision = vinyl_paid_colors.revision + 1 WHERE vinyl_paid_colors.revision = :revision',
        {':key':key,':paid':paid,':revision':revision});
      if(result.rowsAffected!==1){
        await colorView(c.message);await answer(c,'هذا الزر قديم؛ حدّثت القائمة بدون تغيير الحالة.',true);return 'answered';
      }
    }
    await colorView(c.message);return true;
  }
  if(data==='dev_whitelist:open'||data.startsWith('dev_whitelist:remove:')||data.startsWith('dev_whitelist:page:')){
    if(data.startsWith('dev_whitelist:remove:')){
      const id=Number(data.split(':')[2]);
      if(Number.isSafeInteger(id)&&id>0) await db.delete(whitelist).where(eq(whitelist.id,id)).run();
    }
    let page=0;
    if(data.startsWith('dev_whitelist:page:')) {
      const raw=data.slice('dev_whitelist:page:'.length);
      if(!/^\d{1,5}$/.test(raw)){await answer(c,'صفحة غير صحيحة',true);return 'answered';}
      page=Number(raw);
    }
    await whitelistView(c.message,page);return true;
  }
  if(data==='dev_whitelist:add'){
    await updateUser(uid,{pendingAction:'whitelist'});
    await reply(c.message,'أرسل آيدي المستخدم، أو حوّل رسالة منه مع ظهور هوية المرسل.');return true;
  }
  if(['dev_back','dev_limits:back','dev_whitelist:back','dev_text:back'].includes(data)){
    await updateUser(uid,{pendingAction:''});
    await edit(c.message,await tr('MSG_DEV_CHOOSE_TEMPLATE','ar'),await developerKeyboard());return true;
  }
  if(data==='vinyl_menu_image:set'){
    await updateUser(uid,{pendingAction:'menu:photo'});
    await reply(c.message,await tr('MSG_DEV_SEND_MENU_IMAGE','ar')+'\n/cancel_edit');return true;
  }
  if(data.startsWith('dev_text:page:')){
    const [, ,lang,pageString]=data.split(':');
    if(!['ar','en'].includes(lang)||!/^\d{1,5}$/.test(pageString||'')){await answer(c,'صفحة غير صحيحة',true);return 'answered';}
    await textPage(c.message,lang,Number(pageString));return true;
  }
  if(data.startsWith('dev_text:edit:')){
    const [, ,lang,key]=data.split(':');
    if(!['ar','en'].includes(lang)||!(await editPrompt(c.message,uid,key,lang))){
      await answer(c,'المتغيّر غير موجود',true);
      return 'answered';
    }
    return true;
  }
  if(data==='dev_text:menu'){
    await reply(c.message,'✏️ استخدم <code>/search كلمة</code> للبحث في مفاتيح النصوص، أو <code>/edit KEY ar</code> للتعديل.');
    return true;
  }
  return false;
}
export async function adminMessage(message,user){
  const uid=message.from?.id;
  if(message.chat.type!=='private'||!developer(uid))return false;
  const text=String(message.text||'').trim(),action=/^\/(search|edit)(?:@\w+)?(?:\s|$)/.test(text)?'':user?.pendingAction||'';
  if(/^\/cancel_edit(?:@\w+)?$/.test(text)&&action) {
    await updateUser(uid,{pendingAction:''});
    await reply(message,'❌ تم إلغاء التحرير.');return true;
  }
  if(action==='menu:photo'){
    const photos=message.photo;
    if(!Array.isArray(photos)||!photos.length){
      await reply(message,'أرسل صورة، أو /cancel_edit للإلغاء.');return true;
    }
    const fileId=photos[photos.length-1]?.file_id;
    if(!fileId){await reply(message,'ما قدرت أقرأ الصورة، جرّب من جديد.');return true;}
    await db.insert(overrides).values({key:'__vinyl_menu_photo_id',value:fileId,editorId:uid,updatedAt:now()})
      .onConflictDoUpdate({target:overrides.key,set:{value:fileId,editorId:uid,updatedAt:now()}}).run();
    await updateUser(uid,{pendingAction:''});
    await reply(message,await tr('MSG_DEV_MENU_IMAGE_SAVED','ar'));return true;
  }
  if(action==='whitelist'){
    const target=Number(text)||(message.forward_origin?.sender_user?.id)||message.forward_from?.id;
    if(!Number.isSafeInteger(target)||target<=0){
      await reply(message,'أرسل رقماً صحيحاً؛ هوية الرسائل المحوّلة قد تكون مخفية.');return true;
    }
    await db.insert(whitelist).values({id:target,note:'',addedAt:now()})
      .onConflictDoUpdate({target:whitelist.id,set:{id:target}}).run();
    await updateUser(uid,{pendingAction:''});
    await reply(message,'✅ تمت إضافة '+target+' للقائمة البيضاء.');return true;
  }
  if(action.startsWith('edit:')){
    const key=action.slice(5),extracted=extractMessageContent(message);
    const content=extracted?.blocks||message.entities?.length||message.caption_entities?.length||message.rich_message?
      extracted?.html||'':normalizeDevText(extracted?.html||'');
    if(!content.trim()){await reply(message,'أرسل نصاً أو رسالة Rich صالحة.');return true;}
    if(content.length>25000){await reply(message,'النص طويل جداً (الحد 25,000 حرف).');return true;}
    const emojiError=extracted?.blocks?null:emojiSyntaxError(content);
    if(emojiError){await reply(message,'❌ '+emojiError+'\nصحّح النص أو أرسل /cancel_edit.');return true;}
    const rich=message.rich_message?{...(extracted.blocks?{blocks:extracted.blocks}:{html:content}),
      ...(typeof extracted.isRtl==='boolean'?{is_rtl:extracted.isRtl}:{})}:null;
    // Validate with Telegram before saving, retaining the pending edit on rejection.
    let validation;
    try {
      validation=rich?await api.sendRichMessage({chat_id:message.chat.id,rich_message:normalizeRichMedia(rich),disable_notification:true}):
        await api.sendMessage({chat_id:message.chat.id,text:content,parse_mode:'HTML',disable_notification:true});
    } catch(error) {
      if(error?.code!==400)throw error;
      await reply(message,'❌ النص أو الرسالة الغنية غير مقبولة من تليكرام. صحّحها وأرسلها مرة ثانية، أو /cancel_edit.');return true;
    }
    if(validation?.message_id)try{await api.deleteMessage({chat_id:message.chat.id,message_id:validation.message_id});}catch(error){if(error?.code!==400&&error?.code!==403)throw error;}
    const richJson=rich?JSON.stringify(rich):null;
    await db.insert(overrides).values({key,value:content,richJson,editorId:uid,updatedAt:now()})
      .onConflictDoUpdate({target:overrides.key,set:{value:content,richJson,editorId:uid,updatedAt:now()}}).run();
    await updateUser(uid,{pendingAction:''});
    await reply(message,'✅ تم حفظ النص: <code>'+escapeHtml(key)+'</code>');return true;
  }
  if(/^\/search(?:@\w+)?(?:\s|$)/.test(text)){
    const search=text.replace(/^\/search(?:@\w+)?\s*/,'').trim().toLowerCase();
    if(!search){await reply(message,'استخدم <code>/search كلمة</code> للبحث في نصوص العربية والإنكليزية.');return true;}
    const matches=[];
    const custom=new Map((await db.select().from(overrides).all()).map(row=>[row.key,row.value]));
    for(const lang of ['ar','en']){
      const entries=lang==='ar'?ORIGINAL_AR:ORIGINAL_EN;
      for(const [key,value] of Object.entries(entries)){
        const current=custom.get(lang==='en'?'EN::'+key:key)??value;
        if(typeof current==='string'&&(key.toLowerCase().includes(search)||current.toLowerCase().includes(search)))
          matches.push({key,value:current,lang});
      }
    }
    const previews=matches.slice(0,15).map(({key,value,lang})=>
      '• <b>'+escapeHtml(key)+'</b> ['+lang.toUpperCase()+']\n<code>'+
      escapeHtml(value.slice(0,130))+(value.length>130?'…':'')+'</code>');
    await reply(message,matches.length?
      '🔍 نتائج البحث عن <code>'+escapeHtml(search.slice(0,80))+'</code> — '+matches.length+' نتيجة:\n\n'+
      previews.join('\n\n')+(matches.length>15?'\n\n… دقق البحث لنتائج أكثر.':'')+
      '\n\n✏️ للتعديل: <code>/edit KEY ar</code> أو <code>/edit KEY en</code>':
      '🔍 لا توجد نتائج لـ <code>'+escapeHtml(search.slice(0,80))+'</code>');
    return true;
  }
  if(/^\/edit(?:@\w+)?(?:\s|$)/.test(text)){
    const parts=text.split(/\s+/),key=parts[1],lang=parts[2]?.toLowerCase()||(Object.hasOwn(ORIGINAL_AR,key)?'ar':'en');
    if(!key||!['ar','en'].includes(lang)||!(await editPrompt(message,uid,key,lang))) {
      await reply(message,'اكتب <code>/edit KEY ar</code> أو <code>/edit KEY en</code>. استعمل /search لمعرفة المفاتيح.');
    }
    return true;
  }
  return false;
}
