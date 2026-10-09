// Telegram Serverless database: durable state replaces process globals and JSON files.
import { table, integer, text } from 'sdk/db';

export const users = table('vinyl_users', {
  id: integer('id').primaryKey(),
  lang: text('lang').notNull().default('ar'),
  style: text('style').notNull().default('default'),
  rotation: text('rotation').notNull().default('4'),
  used: integer('used').notNull().default(0),
  windowStart: integer('window_start').notNull().default(0),
  premiumUntil: integer('premium_until').notNull().default(0),
  pendingAction: text('pending_action').notNull().default(''),
});
export const whitelist = table('vinyl_whitelist', {
  id: integer('id').primaryKey(),
  note: text('note').notNull().default(''),
  addedAt: integer('added_at').notNull(),
});
export const premiumColors = table('vinyl_paid_colors', {
  key: text('key').primaryKey(),
  paid: integer('paid').notNull().default(1),
});
export const sessions = table('vinyl_sessions', {
  key: text('key').primaryKey(),
  ownerId: integer('owner_id').notNull(),
  chatId: integer('chat_id').notNull(),
  messageId: integer('message_id').notNull(),
  audioId: text('audio_id').notNull(),
  duration: integer('duration').notNull().default(0),
  size: integer('size').notNull().default(0),
  thumbId: text('thumb_id'),
  style: text('style').notNull().default('default'),
  rotation: text('rotation').notNull().default('4'),
  step: text('step').notNull().default('mode'),
  offset: integer('offset').notNull().default(0),
  createdAt: integer('created_at').notNull(),
  expiresAt: integer('expires_at').notNull(),
});
export const receipts = table('vinyl_star_receipts', {
  chargeId: text('charge_id').primaryKey(),
  userId: integer('user_id').notNull(),
  amount: integer('amount').notNull(),
  paidAt: integer('paid_at').notNull(),
});
export const overrides = table('vinyl_custom_texts', {
  key: text('key').primaryKey(),
  value: text('value').notNull(),
  editorId: integer('editor_id').notNull(),
  updatedAt: integer('updated_at').notNull(),
});
export const helpDocs = table('vinyl_help_docs', {
  key: text('key').primaryKey(),
  html: text('html').notNull().default('النص'),
  buttonsJson: text('buttons_json').notNull().default('[]'),
  blocksJson: text('blocks_json'),
  updatedAt: integer('updated_at').notNull().default(0),
});
