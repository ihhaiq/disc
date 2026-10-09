// Pure HTML/text helpers; no Telegram SDK imports (unit-testable in Node).
export const escapeHtml = input => String(input ?? '')
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;');

export const safeUrl = url => /^(https?:\/\/|tg:\/\/)[^\s<>"']+$/i.test(String(url||''));
export const safeHttpUrl = url => /^https?:\/\/[^\s<>"']+$/i.test(String(url||''));
function tag(entity) {
  switch(entity.type) {
    case 'bold': return ['<b>','</b>'];
    case 'italic': return ['<i>','</i>'];
    case 'underline': return ['<u>','</u>'];
    case 'strikethrough': return ['<s>','</s>'];
    case 'spoiler': return ['<tg-spoiler>','</tg-spoiler>'];
    case 'code': return ['<code>','</code>'];
    case 'pre': return ['<pre>','</pre>'];
    case 'blockquote': return ['<blockquote>','</blockquote>'];
    case 'expandable_blockquote': return ['<blockquote expandable>','</blockquote>'];
    case 'text_link':
      return safeUrl(entity.url) ? ['<a href="'+escapeHtml(entity.url)+'">','</a>'] : null;
    case 'custom_emoji':
      return /^\d{1,24}$/.test(String(entity.custom_emoji_id||''))
        ? ['<tg-emoji emoji-id="'+entity.custom_emoji_id+'">','</tg-emoji>'] : null;
    default: return null;
  }
}

// Offsets are UTF-16 code units per Telegram Bot API; includes emoji surrogate pairs.
// Split on entity boundaries to preserve nested style, without corrupting HTML.
export function entitiesToHtml(text, entities=[]) {
  text=String(text??'');
  if(!Array.isArray(entities)||!entities.length)return escapeHtml(text);
  const valid=entities.flatMap((e,i)=>{
    const start=Number(e?.offset),len=Number(e?.length),pair=tag(e||{});
    return Number.isSafeInteger(start)&&Number.isSafeInteger(len)&&len>0&&start>=0&&
      start+len<=text.length&&pair?[{id:i,start,end:start+len,pair}]:[];
  });
  const cuts=[...new Set([0,text.length,...valid.flatMap(e=>[e.start,e.end])])].sort((a,b)=>a-b);
  let html='',opened=[];
  for(let i=0;i<cuts.length-1;i++) {
    const start=cuts[i],end=cuts[i+1];
    const active=valid.filter(e=>e.start<=start&&e.end>=end)
      .sort((a,b)=>a.start-b.start||b.end-a.end||a.id-b.id);
    let match=0;while(match<opened.length&&match<active.length&&opened[match].id===active[match].id)match++;
    for(let j=opened.length-1;j>=match;j--)html+=opened[j].pair[1];
    for(let j=match;j<active.length;j++)html+=active[j].pair[0];
    html+=escapeHtml(text.slice(start,end));
    opened=active;
  }
  for(let i=opened.length-1;i>=0;i--)html+=opened[i].pair[1];
  return html;
}

export function extractMessageContent(message) {
  const r=message?.rich_message;
  if(Array.isArray(r?.blocks)&&r.blocks.length) {
    // Retain original structured blocks. Fallback is only for plain-message clients.
    const plain=String(message.text??message.caption??richTextFallback(r.blocks));
    return {html:entitiesToHtml(plain,message.entities??message.caption_entities),blocks:r.blocks,isRtl:r.is_rtl??null};
  }
  if(typeof r?.html==='string'&&r.html.trim())return {html:r.html,blocks:null,isRtl:r.is_rtl??null};
  const raw=message?.text??message?.caption;
  if(typeof raw!=='string'||!raw.trim())return null;
  const es=message?.text!=null?message?.entities:message?.caption_entities;
  return {html:Array.isArray(es)&&es.length?entitiesToHtml(raw,es):raw,blocks:null,isRtl:null};
}

export function richTextFallback(value) {
  const parts=[];
  function walk(item) {
    if(Array.isArray(item)) {for(const child of item)walk(child);return;}
    if(!item||typeof item!=='object') return;
    for(const [key,child] of Object.entries(item)) {
      if(key==='text'&&typeof child==='string')parts.push(child);
      else if(['caption','summary','title','description','content','items','blocks'].includes(key))walk(child);
    }
  }
  walk(value);
  return parts.filter(Boolean).join('\n').trim()||(value?'🖼️':'');
}

export function normalizeRichMedia(value) {
  if(Array.isArray(value)) return value.map(normalizeRichMedia);
  if(!value||typeof value!=='object') return value;
  const result={};
  for(const [key,child] of Object.entries(value)) {
    if(key==='photo'&&Array.isArray(child)) {
      const photos=child.filter(p=>p?.file_id).sort((a,b)=>(b.width||0)*(b.height||0)-(a.width||0)*(a.height||0));
      result[key]=photos.length?{media:photos[0].file_id}:normalizeRichMedia(child);
    } else if(['photo','video','animation','audio','voice_note','document'].includes(key)&&child?.file_id) {
      result[key]={media:child.file_id};
    } else result[key]=normalizeRichMedia(child);
  }
  return result;
}

export function normalizeDevText(text) {
  text=String(text??'').replace(/!\[(.+?)\]\(tg:\/\/emoji\?id=(\d+)\)/g,
    '<tg-emoji emoji-id="$2">$1</tg-emoji>')
    .replace(/^#{1,6}\s+(.+)$/gm,'<b>$1</b>');
  // Keep code and HTML attributes out of Markdown processing.
  return text.split(/(<code>[\s\S]*?<\/code>|<pre>[\s\S]*?<\/pre>|<[^>]+>|`[^`]+`)/g)
    .map(part=>part.startsWith('<')?part:part.startsWith('`')?'<code>'+escapeHtml(part.slice(1,-1))+'</code>':part
      .replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/__(.+?)__/g,'<b>$1</b>')
      .replace(/\*(.+?)\*/g,'<i>$1</i>').replace(/_(.+?)_/g,'<i>$1</i>')
      .replace(/~~(.+?)~~/g,'<s>$1</s>').replace(/<<(.+?)>>/g,'<u>$1</u>')).join('');
}

export function emojiSyntaxError(text) {
  const opens=text.match(/<tg-emoji\b[^>]*>/g)||[],closes=text.match(/<\/tg-emoji>/g)||[];
  if(opens.length!==closes.length) return 'عدد وسوم الإيموجي غير متطابق.';
  for(const open of opens) if(!/^<tg-emoji\s+emoji-id=["']\d{1,24}["']\s*>$/.test(open)) return 'emoji-id يجب أن يكون آيدي رقمي صحيح.';
  if(/<tg-emoji[^>]*>\s*<\/tg-emoji>/.test(text)) return 'ضع إيموجي أو نصاً داخل الوسم.';
  return null;
}
