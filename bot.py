import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7910999203:AAFEmX2G-q4vw8Mtf8JJ-x1TSCsNzn09Ch4')
ADMIN_ID = int(os.getenv('ADMIN_ID', '8011237487'))  # Replace with your Telegram user ID
QUESTIONS_FILE = 'questions.json'

def load_questions():
    if not os.path.exists(QUESTIONS_FILE):
        return []
    with open(QUESTIONS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_questions(questions):
    with open(QUESTIONS_FILE, 'w', encoding='utf-8') as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Welcome! Send /ask <your question> to submit a question.')

async def ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text('Usage: /ask <your question>')
        return
    question_text = ' '.join(context.args)
    questions = load_questions()
    qid = len(questions) + 1
    question = {
        'id': qid,
        'user_id': update.message.from_user.id,
        'username': update.message.from_user.username,
        'question': question_text,
        'answer': None
    }
    questions.append(question)
    save_questions(questions)
    await update.message.reply_text('Your question has been sent to the admin!')
    # Notify admin
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"New question #{qid} from @{question['username'] or question['user_id']}\n{question_text}"
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text('Unauthorized.')
        return
    keyboard = [
        [InlineKeyboardButton('Show all questions', callback_data='show_questions')],
        [InlineKeyboardButton('Answer a question', callback_data='answer_question')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Admin panel:', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if update.effective_user.id != ADMIN_ID:
        await query.edit_message_text('Unauthorized.')
        return
    if query.data == 'show_questions':
        questions = load_questions()
        if not questions:
            await query.edit_message_text('No questions yet.')
            return
        text = '\n\n'.join([
            f"#{q['id']}: {q['question']}\nAnswer: {q['answer'] or 'Not answered'}" for q in questions
        ])
        await query.edit_message_text(text)
    elif query.data == 'answer_question':
        questions = load_questions()
        unanswered = [q for q in questions if not q['answer']]
        if not unanswered:
            await query.edit_message_text('All questions are answered!')
            return
        keyboard = [[InlineKeyboardButton(f"#{q['id']}: {q['question'][:20]}...", callback_data=f"ans_{q['id']}")] for q in unanswered]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text('Select a question to answer:', reply_markup=reply_markup)
    elif query.data.startswith('ans_'):
        qid = int(query.data.split('_')[1])
        context.user_data['answer_qid'] = qid
        await query.edit_message_text(f'Send your answer for question #{qid}:')

async def answer_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    qid = context.user_data.get('answer_qid')
    if not qid:
        return
    answer = update.message.text
    questions = load_questions()
    for q in questions:
        if q['id'] == qid:
            q['answer'] = answer
            save_questions(questions)
            # Notify user
            await context.bot.send_message(
                chat_id=q['user_id'],
                text=f"Your question: {q['question']}\nAdmin answer: {answer}"
            )
            await update.message.reply_text('Answer sent to user!')
            context.user_data['answer_qid'] = None
            return
    await update.message.reply_text('Question not found.')

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('ask', ask))
    app.add_handler(CommandHandler('admin', admin_panel))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_ID), answer_message))
    app.run_polling() 