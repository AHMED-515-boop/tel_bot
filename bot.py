import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Store questions and answers
questions_db = {}
question_counter = 0

# Admin user ID (you need to set this to your Telegram user ID)
ADMIN_USER_ID = int(os.getenv('8011237487', '8011237487')) or "8011237487"  # Replace with your user ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        'Hi! I\'m a Q&A bot. Send me your question and I\'ll forward it to the admin.\n'
        'The admin will answer and I\'ll send the response back to you!'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = """
Available commands:
/start - Start the bot
/help - Show this help message

How to use:
1. Send me any question as a regular message
2. I'll forward it to the admin
3. The admin will answer and you'll get the response
    """
    await update.message.reply_text(help_text)

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming questions from users."""
    global question_counter
    
    user = update.effective_user
    question = update.message.text
    
    # Skip if message is from admin
    if user.id == ADMIN_USER_ID:
        return
    
    question_counter += 1
    question_id = f"q_{question_counter}"
    
    # Store question details
    questions_db[question_id] = {
        'user_id': user.id,
        'username': user.username or 'Unknown',
        'first_name': user.first_name or 'Unknown',
        'question': question,
        'answered': False
    }
    
    # Confirm receipt to user
    await update.message.reply_text(
        "Thank you for your question! I've forwarded it to the admin. "
        "You'll receive an answer soon."
    )
    
    # Forward to admin with answer button
    if ADMIN_USER_ID:
        admin_message = f"📋 New Question (ID: {question_id})\n\n"
        admin_message += f"👤 From: {user.first_name}"
        if user.username:
            admin_message += f" (@{user.username})"
        admin_message += f"\n🆔 User ID: {user.id}\n\n"
        admin_message += f"❓ Question: {question}"
        
        # Create inline keyboard with answer button
        keyboard = [
            [InlineKeyboardButton("📝 Answer", callback_data=f"answer_{question_id}")],
            [InlineKeyboardButton("❌ Mark as Spam", callback_data=f"spam_{question_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_USER_ID,
                text=admin_message,
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Failed to send message to admin: {e}")

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin button presses."""
    query = update.callback_query
    await query.answer()
    
    # Check if user is admin
    if query.from_user.id != ADMIN_USER_ID:
        await query.edit_message_text("❌ You're not authorized to use this.")
        return
    
    data = query.data
    
    if data.startswith("answer_"):
        question_id = data.replace("answer_", "")
        
        if question_id in questions_db and not questions_db[question_id]['answered']:
            # Update the message to show it's being answered
            await query.edit_message_text(
                query.message.text + "\n\n✏️ **Status: Waiting for your answer...**\n"
                "Please reply to this message with your answer.",
                parse_mode='Markdown'
            )
            
            # Store that admin is answering this question
            context.user_data['answering_question'] = question_id
        else:
            await query.edit_message_text(
                query.message.text + "\n\n❌ **This question has already been answered or doesn't exist.**",
                parse_mode='Markdown'
            )
    
    elif data.startswith("spam_"):
        question_id = data.replace("spam_", "")
        
        if question_id in questions_db:
            questions_db[question_id]['answered'] = True
            await query.edit_message_text(
                query.message.text + "\n\n🚫 **Status: Marked as spam**",
                parse_mode='Markdown'
            )

async def handle_admin_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle admin's answer to a question."""
    # Check if user is admin
    if update.effective_user.id != ADMIN_USER_ID:
        return
    
    # Check if admin is answering a question
    if 'answering_question' not in context.user_data:
        return
    
    question_id = context.user_data['answering_question']
    
    if question_id not in questions_db or questions_db[question_id]['answered']:
        await update.message.reply_text("❌ This question has already been answered or doesn't exist.")
        del context.user_data['answering_question']
        return
    
    answer = update.message.text
    question_data = questions_db[question_id]
    
    # Send answer to the original user
    try:
        answer_message = f"✅ **Answer to your question:**\n\n"
        answer_message += f"❓ Your question: {question_data['question']}\n\n"
        answer_message += f"💬 Admin's answer: {answer}"
        
        await context.bot.send_message(
            chat_id=question_data['user_id'],
            text=answer_message,
            parse_mode='Markdown'
        )
        
        # Mark as answered
        questions_db[question_id]['answered'] = True
        
        # Confirm to admin
        await update.message.reply_text(
            f"✅ Answer sent successfully to {question_data['first_name']}!"
        )
        
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send answer: {str(e)}")
        logger.error(f"Failed to send answer: {e}")
    
    # Clear the answering state
    del context.user_data['answering_question']

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin statistics."""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.message.reply_text("❌ You're not authorized to use this command.")
        return
    
    total_questions = len(questions_db)
    answered_questions = sum(1 for q in questions_db.values() if q['answered'])
    pending_questions = total_questions - answered_questions
    
    stats_message = f"📊 **Bot Statistics**\n\n"
    stats_message += f"📝 Total questions: {total_questions}\n"
    stats_message += f"✅ Answered: {answered_questions}\n"
    stats_message += f"⏳ Pending: {pending_questions}"
    
    await update.message.reply_text(stats_message, parse_mode='Markdown')

def main() -> None:
    """Start the bot."""
    # Get bot token from environment variable
    token = os.getenv('BOT_TOKEN') or "7910999203:AAFEmX2G-q4vw8Mtf8JJ-x1TSCsNzn09Ch4"
    if not token:
        logger.error("BOT_TOKEN environment variable is not set!")
        return
    
    if ADMIN_USER_ID == 0:
        logger.error("ADMIN_USER_ID environment variable is not set!")
        return
    
    # Create the Application
    application = Application.builder().token(token).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("stats", admin_stats))
    application.add_handler(CallbackQueryHandler(handle_admin_callback))
    
    # Handle admin answers (only when admin is answering)
    application.add_handler(MessageHandler(
        filters.TEXT & filters.User(user_id=ADMIN_USER_ID) & ~filters.COMMAND,
        handle_admin_answer
    ))
    
    # Handle regular questions from users
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & ~filters.User(user_id=ADMIN_USER_ID),
        handle_question
    ))
    
    # Start the bot
    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
