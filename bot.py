import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# --- Configuration ---
BOT_TOKEN = os.getenv("BOT_TOKEN") or "7910999203:AAFEmX2G-q4vw8Mtf8JJ-x1TSCsNzn09Ch4"
ADMIN_ID = int(os.getenv("ADMIN_ID", "8011237487"))

# --- Logging ---
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Bot State ---
pending_questions = {}
admin_answer_state = {}  # Stores: { admin_id: { "question_id": Q1, "message_id": 123 } }
question_counter = 1

def update_question_counter():
    global question_counter
    if pending_questions:
        ids = [int(k[1:]) for k in pending_questions if k.startswith("Q") and k[1:].isdigit()]
        question_counter = max(ids) + 1 if ids else 1
    else:
        question_counter = 1

def save_question(user_id, username, question, question_id):
    pending_questions[question_id] = {
        'user_id': user_id,
        'username': username,
        'question': question,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'pending'
    }

# --- Start Command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id == ADMIN_ID:
        await update.message.reply_text("👨‍💼 أهلاً بالأدمن! استخدم /pending /stats /reset_counter")
    else:
        await update.message.reply_text("👋 مرحباً! أرسل سؤالك هنا، وسنقوم بالرد عليك.")

# --- Handle Incoming Question ---
async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global question_counter
    user = update.effective_user
    text = update.message.text

    # Admin is replying
    if user.id == ADMIN_ID:
        await handle_admin_reply(update, context)
        return

    # New user question
    question_id = f"Q{question_counter}"
    save_question(user.id, user.username or user.first_name, text, question_id)
    question_counter += 1

    await update.message.reply_text(f"✅ تم استلام سؤالك!\n🆔 رقم: {question_id}")

    # Send to admin
    keyboard = [
        [InlineKeyboardButton("📝 إرسال إجابة", callback_data=f"answer_{question_id}")],
        [InlineKeyboardButton("🗑️ حذف السؤال", callback_data=f"delete_{question_id}")],
        [InlineKeyboardButton("🔄 إعادة ضبط العداد", callback_data="reset_counter")]
    ]
    msg = (
        f"📩 *سؤال جديد!*\n\n"
        f"🆔 `{question_id}`\n"
        f"👤 {user.first_name} (@{user.username})\n"
        f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"❓ {text}"
    )
    sent_msg = await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=msg,
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    # Save the message_id for later deletion
    admin_answer_state["last_question"] = {
        "question_id": question_id,
        "message_id": sent_msg.message_id
    }

# --- Admin Reply ---
async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if "question_id" not in admin_answer_state.get(ADMIN_ID, {}):
        await update.message.reply_text("❗ اضغط أولاً على زر (📝 إرسال إجابة).")
        return

    question_id = admin_answer_state[ADMIN_ID]["question_id"]
    message_id_to_delete = admin_answer_state[ADMIN_ID]["message_id"]

    if question_id not in pending_questions:
        await update.message.reply_text("❌ السؤال غير موجود.")
        del admin_answer_state[ADMIN_ID]
        return

    answer = update.message.text
    q_data = pending_questions[question_id]
    user_id = q_data['user_id']

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=(
                f"✅ *تم الرد على سؤالك!*\n\n"
                f"🆔 {question_id}\n"
                f"❓ {q_data['question']}\n\n"
                f"💬 {answer}"
            ),
            parse_mode='Markdown'
        )
        # Mark answered
        q_data['status'] = 'answered'
        q_data['answer'] = answer
        q_data['answered_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # Confirm to admin
        await update.message.reply_text("✅ تم إرسال الإجابة.")

        # 🔥 Delete the admin's question message
        try:
            await context.bot.delete_message(chat_id=ADMIN_ID, message_id=message_id_to_delete)
        except Exception as e:
            logger.warning(f"Failed to delete admin message: {e}")

    except Exception as e:
        await update.message.reply_text(f"❌ فشل إرسال الإجابة: {e}")

    del admin_answer_state[ADMIN_ID]

# --- Show Pending Questions ---
async def show_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    pending = {k: v for k, v in pending_questions.items() if v['status'] == 'pending'}
    if not pending:
        await update.message.reply_text("✅ لا توجد أسئلة معلقة.")
        return

    for question_id, data in sorted(pending.items(), key=lambda x: int(x[0][1:])):
        text = (
            f"🆔 `{question_id}`\n"
            f"👤 {data['username']} (ID: {data['user_id']})\n"
            f"⏰ {data['timestamp']}\n\n"
            f"❓ {data['question']}"
        )
        keyboard = [
            [InlineKeyboardButton("📝 إرسال إجابة", callback_data=f"answer_{question_id}")],
            [InlineKeyboardButton("🗑️ حذف السؤال", callback_data=f"delete_{question_id}")]
        ]
        msg = await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=text,
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        admin_answer_state["last_question"] = {
            "question_id": question_id,
            "message_id": msg.message_id
        }

# --- Show Stats ---
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total = len(pending_questions)
    answered = sum(1 for q in pending_questions.values() if q['status'] == 'answered')
    pending = total - answered
    await update.message.reply_text(
        f"📊 إحصائيات:\n"
        f"📥 الكل: {total}\n"
        f"✅ تم الرد: {answered}\n"
        f"⏳ معلق: {pending}"
    )

# --- Reset Counter ---
async def reset_counter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    global question_counter
    question_counter = 1
    await update.message.reply_text("🔄 تم إعادة تعيين العداد إلى Q1.")

# --- Button Actions ---
async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ غير مصرح.")
        return

    data = query.data
    if data.startswith("answer_"):
        qid = data.split("_")[1]
        if qid in pending_questions:
            admin_answer_state[ADMIN_ID] = {
                "question_id": qid,
                "message_id": query.message.message_id
            }
            await query.edit_message_text(f"✏️ أرسل الآن إجابتك للسؤال `{qid}`", parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ السؤال غير موجود.")

    elif data.startswith("delete_"):
        qid = data.split("_")[1]
        if qid in pending_questions:
            del pending_questions[qid]
            await query.edit_message_text(f"🗑️ تم حذف السؤال {qid}.")

    elif data == "reset_counter":
        global question_counter
        question_counter = 1
        await query.edit_message_text("🔄 تم إعادة ضبط العداد إلى Q1.")

# --- Error Logging ---
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception:", exc_info=context.error)

# --- Main Function ---
def main():
    update_question_counter()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pending", show_pending))
    app.add_handler(CommandHandler("stats", show_stats))
    app.add_handler(CommandHandler("reset_counter", reset_counter_cmd))
    app.add_handler(CallbackQueryHandler(handle_buttons))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(user_id=ADMIN_ID), handle_admin_reply))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))

    app.add_error_handler(error_handler)

    print("✅ Bot is running...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
