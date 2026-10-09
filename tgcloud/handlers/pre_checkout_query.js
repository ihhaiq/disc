import { api } from 'sdk';
import { CONFIG } from '../lib/config.js';
import { validatePayment } from '../lib/payments.js';
export default async function(q) {
  if(!q?.id||!q.from)return;
  const valid=CONFIG.RENDERER_ENABLED && validatePayment(q.invoice_payload,q.currency,q.total_amount,q.from.id);
  await api.answerPreCheckoutQuery({
    pre_checkout_query_id:q.id,ok:Boolean(valid),
    ...(!valid?{error_message:'هذه الباقة غير متاحة للبيع حالياً حتى يكتمل تحويل الفيديو في نسخة السيرفليس.'}:{})
  });
}
