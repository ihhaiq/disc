// No in-memory process globals: each callback may run in a different isolate.
import { db } from 'sdk';
import { eq } from 'sdk/db';
import { users, sessions, whitelist, premiumColors, receipts } from '../schema.js';
import { CONFIG, now, developer } from './config.js';
export async function getUser(uid) {
  if (!uid) return null;
  await db.insert(users).values({ id: uid, windowStart: now() })
    .onConflictDoUpdate({ target: users.id, set:{ id:uid } }).run();
  return db.select().from(users).where(eq(users.id, uid)).get();
}
export async function updateUser(uid, patch) {
  await getUser(uid);
  await db.update(users).set(patch).where(eq(users.id, uid)).run();
}
export async function isExempt(uid) {
  return developer(uid) || !!(await db.select().from(whitelist).where(eq(whitelist.id, uid)).get());
}
export async function premium(uid) {
  if(await isExempt(uid))return true;
  return (await recomputePremium(uid)) > now();
}
export async function colorPaid(key) {
  const entry=await db.select().from(premiumColors).where(eq(premiumColors.key, key)).get();
  return Boolean(entry?.paid);
}
export async function canUseColor(uid, key) { return !(await colorPaid(key)) || await premium(uid); }
export async function limitStatus(uid) {
  const user=await getUser(uid), exempt=await isExempt(uid);
  const start= user.windowStart || now(), elapsed=now()-start;
  const reset=elapsed>=86400;
  const used=reset?0:user.used, limit=await premium(uid)?CONFIG.PREMIUM_DAILY_LIMIT:CONFIG.FREE_DAILY_LIMIT;
  return { used, limit, remaining:exempt?Infinity:Math.max(0,limit-used), resetSeconds:reset?86400:Math.max(0,86400-elapsed) };
}
export async function finishUse(uid) {
  // Only call AFTER a successful sendVideoNote. Never bill attempted or failed renders.
  const u=await getUser(uid), reset=now()-u.windowStart>=86400;
  await db.update(users).set({used:reset?1:u.used+1,windowStart:reset?now():u.windowStart})
    .where(eq(users.id,uid)).run();
}
export function sessionKey(chatId,ownerId,messageId,kind='private') {
  return kind==='private' ? 'u'+ownerId : (kind==='channel'?'c':'g')+chatId+':'+messageId;
}
export async function getSession(key) {
  const s=await db.select().from(sessions).where(eq(sessions.key,key)).get();
  if (!s) return null;
  if (s.expiresAt<=now()) { await db.delete(sessions).where(eq(sessions.key,key)).run(); return null; }
  return s;
}
export async function saveSession(data) {
  await db.insert(sessions).values(data).onConflictDoUpdate({
    target:sessions.key,
    set: { ...data },
  }).run();
}
export async function patchSession(key,patch) {
  await db.update(sessions).set(patch).where(eq(sessions.key,key)).run();
}
export async function deleteSession(key) { await db.delete(sessions).where(eq(sessions.key,key)).run(); }
export async function recomputePremium(uid) {
  // The immutable receipt ledger, not an incremental counter, is the source of truth.
  // A process interruption between insert and account update is repaired on read.
  const rows=await db.select().from(receipts).where(eq(receipts.userId,uid)).all();
  rows.sort((a,b)=>(a.paidAt-b.paidAt)||a.chargeId.localeCompare(b.chargeId));
  let expires=0;
  for(const p of rows)expires=Math.max(expires,p.paidAt)+CONFIG.STARS_SUBSCRIPTION_DAYS*86400;
  const u=await getUser(uid);
  if(expires>u.premiumUntil) await db.update(users).set({premiumUntil:expires})
    .where(eq(users.id,uid)).run();
  return Math.max(expires,u.premiumUntil);
}
export async function addReceipt(payment,uid) {
  const chargeId = payment.telegram_payment_charge_id;
  if (!chargeId) return false;
  const r=await db.run('INSERT OR IGNORE INTO vinyl_star_receipts (charge_id,user_id,amount,paid_at) VALUES (:id,:uid,:amount,:ts)',
    {':id':chargeId, ':uid':uid, ':amount':payment.total_amount, ':ts':now()});
  await recomputePremium(uid); // safe on duplicates; recover from interrupted credits
  return r.rowsAffected===1;
}
