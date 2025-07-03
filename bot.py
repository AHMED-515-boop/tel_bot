import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# إعداد السجلات
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# التوكن والمعرّف
BOT_TOKEN = os.environ.get('BOT_TOKEN') or "7910999203:AAFEmX2G-q4vw8Mtf8JJ-x1TSCsNzn09Ch4"
ADMIN_ID = int(os.environ.get('ADMIN_ID', '8011237487'))

# المتغيرات العامة
pending_questions = {}
admin_answer_state = {}
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id == ADMIN_ID:
        await update.message.reply_text(
            "👨‍💼 أهلاً بك أيها الأدمن!\n\n"
            "/pending - عرض الأسئلة المعلقة\n"
            "/stats - الإحصائيات\n"
            "/reset_counter - إعادة تعيين العداد"
        )
    else:
        await update.message.reply_text(
            f"مرحباً {user.first_name} 👋\n"
            "أرسل سؤالك هنا وسنقوم بالرد عليك قريباً! 📝"
        )

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global question_counter
    user = update.effective_user
    question = update.message.text

    # تجاهل الأسئلة من الأدمن (يستخدم الرد من الزر)
    if user.id == ADMIN_ID:
        await handle_admin_reply(update, context)
        return

    question_id = f"Q{question_counter}"
    save_question(user.id, user.username or user.first_name, question, question_id)
    question_counter += 1

    await update.message.reply_text(
        f"✅ تم استلام سؤالك!\n🆔 رقم السؤال: {question_id}\n⏰ {datetime.now().strftime('%H:%M')}"
    )

    keyboard = [
        [InlineKeyboardButton("📝 إرسال إجابة", callback_data=f"answer_{question_id}")],
        [InlineKeyboardButton("🗑️ حذف السؤال", callback_data=f"delete_{question_id}")],
        [InlineKeyboardButton("🔄 إعادة ضبط العداد", callback_data="reset_counter")]
    ]

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"📩 *سؤال جديد!*\n\n"
            f"🆔 `{question_id}`\n"
            f"👤 من: {user.first_name} (@{user.username})\n"
            f"❓ {question}\n"
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ),
        parse_mode='Markdown',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ هذا الزر مخصص للأدمن فقط.")
        return

    data = query.data

    if data.startswith("answer_"):
        qid = data.split("_")[1]
        if qid in pending_questions:
            admin_answer_state[ADMIN_ID] = qid
            await query.edit_message_text(f"✏️ اكتب الآن إجابتك على السؤال `{qid}`", parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ السؤال غير موجود.")

    elif data.startswith("delete_"):
        qid = data.split("_")[1]
        if qid in pending_questions:
            del pending_questions[qid]
            await query.edit_message_text(f"🗑️ تم حذف السؤال {qid}.")
        else:
            await query.edit_message_text("❌ لم يتم العثور على السؤال.")

    elif data == "reset_counter":
        global question_counter
        question_counter = 1
        await query.edit_message_text(
            "🔄 تم إعادة تعيين عداد الأسئلة. التالي سيكون: Q1",
            parse_mode='Markdown'
        )

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if ADMIN_ID not in admin_answer_state:
        await update.message.reply_text("❗ اضغط على زر (📝 إرسال إجابة) أولاً لاختيار سؤال.")
        return

    question_id = admin_answer_state[ADMIN_ID]
    if question_id not in pending_questions:
        await update.message.reply_text("❌ لم يتم العثور على السؤال.")
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
                f"❓ سؤالك:\n{q_data['question']}\n\n"
                f"💬 الإجابة:\n{answer}"
            ),
            parse_mode='Markdown'
        )
        q_data['status'] = 'answered'
        q_data['answer'] = answer
        q_data['answered_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        await update.message.reply_text(f"✅ تم إرسال الإجابة للسؤال {question_id}.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ في الإرسال: {str(e)}")

    del admin_answer_state[ADMIN_ID]

async def show_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    pending = [f"`{k}` - {v['username']}" for k, v in pending_questions.items() if v['status'] == 'pending']
    if not pending:
        await update.message.reply_text("✅ لا توجد أسئلة معلقة.")
    else:
        await update.message.reply_text("🕐 *الأسئلة المعلقة:*\n" + "\n".join(pending), parse_mode='Markdown')

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    total = len(pending_questions)
    answered = sum(1 for q in pending_questions.values() if q['status'] == 'answered')
    pending = total - answered
    await update.message.reply_text(
        f"📊 الإحصائيات:\n"
        f"📦 إجمالي: {total}\n"
        f"✅ مُجاب عليها: {answered}\n"
        f"⏳ في الانتظار: {pending}",
        parse_mode='Markdown'
    )

async def reset_counter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    global question_counter
    question_counter = 1
    await update.message.reply_text("🔄 تم إعادة تعيين عداد الأسئلة. التالي سيكون: Q1")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Error:", exc_info=context.error)

def main():
    update_question_counter()
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pending", show_pending))
    app.add_handler(CommandHandler("stats", show_stats))
    app.add_handler(CommandHandler("reset_counter", reset_counter_cmd))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.User(user_id=ADMIN_ID), handle_admin_reply))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))
    app.add_error_handler(error_handler)

    print("✅ البوت يعمل الآن...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
