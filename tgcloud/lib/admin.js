import { api, db } from 'sdk';
import { eq } from 'sdk/db';
import { users, whitelist, premiumColors, overrides } from '../schema.js';
import { CONFIG, developer, now } from './config.js';
import { STYLES } from './catalog.js';
import { DEV_MENU, kb } from './keyboard.js';
import { getUser, updateUser, colorPaid } from './state.js';
import { reply, edit, answer } from './io.js';
import { STR } from './i18n.js';
import { ORIGINAL_AR, ORIGINAL_EN } from './original-texts.js';
import { escapeHtml, extractMessageContent } from './dev-text-utils.js';

const btn=(text,callback_data)=>({text,callback_data});
export async function devStart(message) {
  if(!developer(message.from?.id)) return false;
  await reply(message,'🎨 لوحة مطور Vinyl Bot\n\n<code>/search كلمة</code> — البحث في النصوص\n<code>/edit KEY [ar|en]</code> — تعديل نص',DEV_MENU);
  return true;
}
const TEXTS_PER_PAGE=5;
const choices=lang=>Object.keys(lang==='en'?{...ORIGINAL_EN,...STR.en}:{...ORIGINAL_AR,...STR.ar})
  .filter(k=>!k.startsWith('__')).sort((a,b)=>a.localeCompare(b));
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
  rows.push([btn('🔙 رجوع','dev_back')]);
  await edit(chatMessage,'✏️ تحرير النصوص ('+(lang==='en'?'English':'عربي')+
    ') — صفحة '+(page+1)+'/'+(last+1)+' ('+keys.length+' متغيّر):',kb(rows));
}
async function editPrompt(message,uid,key,lang){
  const dict=lang==='en'?{...ORIGINAL_EN,...STR.en}:{...ORIGINAL_AR,...STR.ar};
  if(!Object.hasOwn(dict,key))return false;
  const dbKey=lang==='en'?'EN::'+key:key;
  const edited=await db.select().from(overrides).where(eq(overrides.key,dbKey)).get();
  const value=String(edited?.value??dict[key]);
  await updateUser(uid,{pendingAction:'edit:'+dbKey});
  await reply(message,'📝 القيمة الحالية لـ <code>'+escapeHtml(key)+'</code> ('+
    (lang==='en'?'English':'عربي')+'):\n\n<code>'+escapeHtml(value.slice(0,500))+
    (value.length>500?'…':'')+'</code>\n\nأرسل النص أو رسالة Rich جديدة. للإلغاء: /cancel_edit');
  return true;
}
async function whitelistView(chatMessage){
  const rows=await db.select().from(whitelist).all();
  const names=rows.map(x=>x.id);
  const markup=kb([...names.slice(0,25).map(id=>[btn('❌ إزالة '+id,'dev_whitelist:remove:'+id)]),[btn('➕ إضافة مستخدم','dev_whitelist:add')],[btn('🔙 رجوع','dev_back')]]);
  await edit(chatMessage,'🛡️ القائمة البيضاء (مستثناة من الحدود اليومية):\n\n'+(names.join('\n')||'لا يوجد مستخدمون.'),markup);
}
async function colorView(chatMessage){
  const rows=[];
  for(const s of STYLES){
    const paid=await colorPaid(s.key);
    rows.push([btn(s.ar+' — '+(paid?'💎':'🆓'),'dev_limits:toggle:'+s.key)]);
  }
  rows.push([btn('🔙 رجوع','dev_back')]);
  await edit(chatMessage,'🔒 الأقراص المتوفرة:\nاضغط أي قرص للتبديل بين مجاني ومدفوع.',kb(rows));
}
export async function developerCallback(c,data){
  const uid=c.from.id;
  if(!developer(uid)){await answer(c,'هذا الخيار للمطور فقط',true);return true;}
  if(data==='dev_limits:open'||data.startsWith('dev_limits:toggle:')){
    if(data.startsWith('dev_limits:toggle:')){
      const key=data.split(':')[2];if(!STYLES.some(x=>x.key===key)){await answer(c,'قرص غير معروف',true);return true;}
      const paid=await colorPaid(key);
      await db.insert(premiumColors).values({key,paid:paid?0:1})
        .onConflictDoUpdate({target:premiumColors.key,set:{paid:paid?0:1}}).run();
    }
    await colorView(c.message);return true;
  }
  if(data==='dev_whitelist:open'||data.startsWith('dev_whitelist:remove:')){
    if(data.startsWith('dev_whitelist:remove:')){
      const id=Number(data.split(':')[2]);
      if(Number.isSafeInteger(id)) await db.delete(whitelist).where(eq(whitelist.id,id)).run();
    }
    await whitelistView(c.message);return true;
  }
  if(data==='dev_whitelist:add'){
    await updateUser(uid,{pendingAction:'whitelist'});
    await reply(c.message,'أرسل آيدي المستخدم، أو حوّل رسالة منه مع ظهور هوية المرسل.');return true;
  }
  if(data==='dev_back'){await edit(c.message,'🎨 لوحة المطور',DEV_MENU);return true;}
  if(data==='vinyl_menu_image:set'){
    await updateUser(uid,{pendingAction:'menu:photo'});
    await reply(c.message,'🖼 أرسل صورة جديدة لقائمة الأقراص، أو /cancel_edit للإلغاء.');return true;
  }
  if(data.startsWith('dev_text:page:')){
    const [, ,lang,pageString]=data.split(':');
    if(!['ar','en'].includes(lang)||!/^\d{1,5}$/.test(pageString||'')){await answer(c,'صفحة غير صحيحة',true);return true;}
    await textPage(c.message,lang,Number(pageString));return true;
  }
  if(data.startsWith('dev_text:edit:')){
    const [, ,lang,key]=data.split(':');
    if(!['ar','en'].includes(lang)||!(await editPrompt(c.message,uid,key,lang))){
      await answer(c,'المتغيّر غير موجود',true);
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
  if(!developer(uid))return false;
  const text=String(message.text||'').trim(),action=user?.pendingAction||'';
  if(text==='/cancel_edit'&&action) {
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
    await reply(message,'✅ تم حفظ صورة قائمة الأقراص.');return true;
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
    const content=extracted?.html||'';
    if(!content.trim()){await reply(message,'أرسل نصاً أو رسالة Rich صالحة.');return true;}
    if(content.length>25000){await reply(message,'النص طويل جداً (الحد 25,000 حرف).');return true;}
    await db.insert(overrides).values({key,value:content,editorId:uid,updatedAt:now()})
      .onConflictDoUpdate({target:overrides.key,set:{value:content,editorId:uid,updatedAt:now()}}).run();
    await updateUser(uid,{pendingAction:''});
    await reply(message,'✅ تم حفظ النص: <code>'+escapeHtml(key)+'</code>');return true;
  }
  if(text==='/search'||text.startsWith('/search ')){
    const search=text.slice(7).trim().toLowerCase();
    if(!search){await reply(message,'استخدم <code>/search كلمة</code> للبحث في نصوص العربية والإنكليزية.');return true;}
    const matches=[];
    for(const lang of ['ar','en']){
      const entries=lang==='ar'?{...ORIGINAL_AR,...STR.ar}:{...ORIGINAL_EN,...STR.en};
      for(const [key,value] of Object.entries(entries)){
        if(typeof value==='string'&&(key.toLowerCase().includes(search)||value.toLowerCase().includes(search)))
          matches.push({key,value,lang});
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
  if(text==='/edit'||text.startsWith('/edit ')){
    const parts=text.split(/\s+/),key=parts[1],lang=parts[2]||'ar';
    if(!key||!['ar','en'].includes(lang)||!(await editPrompt(message,uid,key,lang))) {
      await reply(message,'اكتب <code>/edit KEY ar</code> أو <code>/edit KEY en</code>. استعمل /search لمعرفة المفاتيح.');
    }
    return true;
  }
  return false;
}
