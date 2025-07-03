import os
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# --- Configuration ---
BOT_TOKEN = "7910999203:AAFEmX2G-q4vw8Mtf8JJ-x1TSCsNzn09Ch4"  # 🔒 Replace with your bot token from @BotFather
ADMIN_USER_ID = "8011237487"     # 👤 Replace with your Telegram user ID

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Storage ---
questions_db = {}
question_counter = 0
QUESTIONS_FILE = "questions.json"

def load_questions():
    global questions_db, question_counter
    if os.path.exists(QUESTIONS_FILE):
        with open(QUESTIONS_FILE, "r") as f:
            questions_db = json.load(f)
        question_counter = len(questions_db)

def save_questions():
    with open(QUESTIONS_FILE, "w") as f:
        json.dump(questions_db, f)

# --- Bot Commands ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "👋 Hi! I'm a Q&A bot.\n\n"
        "❓ Send me a question and I’ll forward it to the admin.\n"
        "📬 You'll get a reply as soon as the admin answers."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🛠 Available commands:\n"
        "/start - Start the bot\n"
        "/help - Show this help message\n"
        "/stats - (Admin only) Show stats"
    )

# --- User Question Handling ---
async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global question_counter
    user = update.effective_user
    question = update.message.text

    if user.id == ADMIN_USER_ID:
        return

    question_counter += 1
    question_id = f"q_{question_counter}"

    questions_db[question_id] = {
        'user_id': user.id,
        'username': user.username or 'Unknown',
        'first_name': user.first_name or 'Unknown',
        'question': question,
        'answered': False
    }
    save_questions()

    await update.message.reply_text("✅ Question received! The admin will reply soon.")

    admin_message = (
        f"📋 *New Question* (ID: `{question_id}`)\n\n"
        f"👤 From: {user.first_name}" +
        (f" (@{user.username})" if user.username else "") +
        f"\n🆔 User ID: `{user.id}`\n\n"
        f"❓ *Question:*\n{question}"
    )

    keyboard = [
        [InlineKeyboardButton("📝 Answer", callback_data=f"answer_{question_id}")],
        [InlineKeyboardButton("❌ Mark as Spam", callback_data=f"spam_{question_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(
            chat_id=ADMIN_USER_ID,
            text=admin_message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Failed to send to admin: {e}", exc_info=True)

# --- Admin Button Handler ---
async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_USER_ID:
        await query.edit_message_text("❌ You're not authorized.")
        return

    data = query.data

    if data.startswith("answer_"):
        question_id = data.replace("answer_", "")
        if question_id in questions_db and not questions_db[question_id]['answered']:
            await query.edit_message_text(
                query.message.text + "\n\n✏️ *Waiting for your answer...*",
                parse_mode="Markdown"
            )
            context.user_data['answering_question'] = question_id
        else:
            await query.edit_message_text(
                query.message.text + "\n\n❌ Already answered or invalid.",
                parse_mode="Markdown"
            )
    elif data.startswith("spam_"):
        question_id = data.replace("spam_", "")
        if question_id in questions_db:
            questions_db[question_id]['answered'] = True
            save_questions()
            await query.edit_message_text(
                query.message.text + "\n\n🚫 *Marked as spam.*",
                parse_mode="Markdown"
            )

# --- Admin Answer Handler ---
async def handle_admin_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_USER_ID:
        return

    if 'answering_question' not in context.user_data:
        return

    question_id = context.user_data['answering_question']
    if question_id not in questions_db or questions_db[question_id]['answered']:
        await update.message.reply_text("❌ Question not found or already answered.")
        del context.user_data['answering_question']
        return

    answer = update.message.text
    q = questions_db[question_id]

    message = (
        f"✅ *Answer to your question:*\n\n"
        f"❓ *Your question:*\n{q['question']}\n\n"
        f"💬 *Admin's answer:*\n{answer}"
    )

    try:
        await context.bot.send_message(
            chat_id=q['user_id'],
            text=message,
            parse_mode="Markdown"
        )
        questions_db[question_id]['answered'] = True
        save_questions()
        await update.message.reply_text("✅ Answer sent.")
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send: {e}")
        logger.error(f"Send error: {e}", exc_info=True)

    del context.user_data['answering_question']

# --- Admin Stats ---
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ Not authorized.")
        return

    total = len(questions_db)
    answered = sum(1 for q in questions_db.values() if q['answered'])
    pending = total - answered

    stats = (
        "📊 *Stats:*\n"
        f"📝 Total: {total}\n"
        f"✅ Answered: {answered}\n"
        f"⏳ Pending: {pending}"
    )
    await update.message.reply_text(stats, parse_mode="Markdown")

# --- Main Entry ---
def main():
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN missing!")
        return

    if not ADMIN_USER_ID:
        logger.error("❌ ADMIN_USER_ID not set!")
        return

    load_questions()

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CallbackQueryHandler(handle_admin_callback))

    application.add_handler(MessageHandler(
        filters.TEXT & filters.User(user_id=ADMIN_USER_ID) & ~filters.COMMAND,
        handle_admin_answer
    ))

    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.User(user_id=ADMIN_USER_ID),
        handle_question
    ))

    logger.info("🤖 Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
