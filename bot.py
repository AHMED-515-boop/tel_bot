# requirements.txt
python-telegram-bot==20.7
sqlite3

# Procfile
web: python main.py

# railway.json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}

# .env (create this file and add your variables)
BOT_TOKEN="7910999203:AAFEmX2G-q4vw8Mtf8JJ-x1TSCsNzn09Ch4"
ADMIN_CHAT_ID="8011237487"

# main.py (Updated version for Railway deployment)
import logging
import json
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from datetime import datetime
import sqlite3
from pathlib import Path

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration - Using environment variables for Railway
BOT_TOKEN = os.getenv('BOT_TOKEN') or "7910999203:AAFEmX2G-q4vw8Mtf8JJ-x1TSCsNzn09Ch4"
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID') or "8011237487"

# Validate environment variables
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")
if not ADMIN_CHAT_ID:
    raise ValueError("ADMIN_CHAT_ID environment variable is required")

class SupportBot:
    def __init__(self):
        self.db_path = Path("support_bot.db")
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database for storing questions and answers"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        
        # Create tables
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                question TEXT,
                timestamp DATETIME,
                status TEXT DEFAULT 'pending',
                admin_reply TEXT,
                reply_timestamp DATETIME
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                username TEXT
            )
        ''')
        
        self.conn.commit()
        logger.info("Database initialized successfully")
    
    def add_admin(self, user_id, username):
        """Add admin to database"""
        self.cursor.execute(
            "INSERT OR REPLACE INTO admins (user_id, username) VALUES (?, ?)",
            (user_id, username)
        )
        self.conn.commit()
    
    def is_admin(self, user_id):
        """Check if user is admin"""
        self.cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
        return self.cursor.fetchone() is not None
    
    def save_question(self, user_id, username, question):
        """Save user question to database"""
        self.cursor.execute(
            "INSERT INTO questions (user_id, username, question, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, username, question, datetime.now())
        )
        self.conn.commit()
        return self.cursor.lastrowid
    
    def get_pending_questions(self):
        """Get all pending questions"""
        self.cursor.execute(
            "SELECT id, user_id, username, question, timestamp FROM questions WHERE status = 'pending' ORDER BY timestamp DESC"
        )
        return self.cursor.fetchall()
    
    def get_question_by_id(self, question_id):
        """Get specific question by ID"""
        self.cursor.execute(
            "SELECT id, user_id, username, question, timestamp FROM questions WHERE id = ?",
            (question_id,)
        )
        return self.cursor.fetchone()
    
    def update_question_status(self, question_id, status, admin_reply=None):
        """Update question status and admin reply"""
        if admin_reply:
            self.cursor.execute(
                "UPDATE questions SET status = ?, admin_reply = ?, reply_timestamp = ? WHERE id = ?",
                (status, admin_reply, datetime.now(), question_id)
            )
        else:
            self.cursor.execute(
                "UPDATE questions SET status = ? WHERE id = ?",
                (status, question_id)
            )
        self.conn.commit()

# Initialize bot instance
support_bot = SupportBot()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    welcome_message = f"""
🤖 Welcome to Support Bot, {user.first_name}!

I'm here to help you get support from our administrators.

📝 Simply send me your question and I'll forward it to our admin team.
⏰ You'll receive a response as soon as possible.

Commands:
/help - Show this help message
/status - Check your question status (for admins)
/questions - View pending questions (admin only)
"""
    
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
🆘 *Support Bot Help*

*For Users:*
• Send any message with your question
• I'll forward it to our admin team
• Wait for a response from administrators

*For Admins:*
• `/questions` - View all pending questions
• `/status` - Check bot status
• Reply to forwarded messages to answer questions

*How it works:*
1. User sends a question
2. Bot forwards to admin
3. Admin replies to the forwarded message
4. Bot sends admin's reply back to user
"""
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle user questions"""
    user = update.effective_user
    question = update.message.text
    
    # Don't process commands as questions
    if question.startswith('/'):
        return
    
    # Save question to database
    question_id = support_bot.save_question(
        user.id, 
        user.username or user.first_name, 
        question
    )
    
    # Send confirmation to user
    await update.message.reply_text(
        f"✅ Your question has been received!\n\n"
        f"Question ID: #{question_id}\n"
        f"Our admin team will respond soon."
    )
    
    # Forward to admin with inline keyboard
    admin_keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("💬 Reply", callback_data=f"reply_{question_id}"),
            InlineKeyboardButton("✅ Quick Answer", callback_data=f"answer_{question_id}")
        ],
        [
            InlineKeyboardButton("❌ Close", callback_data=f"close_{question_id}"),
            InlineKeyboardButton("📋 View All", callback_data=f"viewall")
        ]
    ])
    
    admin_message = f"""
🔔 *New Question Received*

*From:* {user.first_name} (@{user.username or 'No username'})
*User ID:* `{user.id}`
*Question ID:* #{question_id}
*Time:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

*Question:*
{question}

📝 *Instructions:*
• Click "💬 Reply" to send a custom response
• Click "✅ Quick Answer" for common responses
• Click "❌ Close" to mark as resolved
"""
    
    try:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=admin_message,
            reply_markup=admin_keyboard,
            parse_mode='Markdown'
        )
        logger.info(f"Question #{question_id} forwarded to admin")
    except Exception as e:
        logger.error(f"Failed to send message to admin: {e}")

async def handle_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin callback buttons"""
    query = update.callback_query
    user_id = query.from_user.id
    
    # Check if user is admin
    if not support_bot.is_admin(user_id):
        await query.answer("❌ You are not authorized to use this feature.")
        return
    
    data = query.data
    
    if data == "viewall":
        await query.answer("📋 Loading all questions...")
        await view_questions_inline(update, context)
        return
    
    action, question_id = data.split('_')
    question_id = int(question_id)
    
    if action == "reply":
        await query.answer("💬 Please type your reply message.")
        # Store the question ID in user data for the next message
        context.user_data['replying_question'] = question_id
        
        # Show a prompt message
        await query.message.reply_text(
            f"💬 *Replying to Question #{question_id}*\n\n"
            f"Please type your reply message below. It will be sent directly to the user.\n\n"
            f"Type /cancel to cancel this reply.",
            parse_mode='Markdown'
        )
        
    elif action == "answer":
        # Show quick answer options
        quick_answers_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Thank you for your question", callback_data=f"quick_thanks_{question_id}")],
            [InlineKeyboardButton("⏳ We're working on it", callback_data=f"quick_working_{question_id}")],
            [InlineKeyboardButton("📞 Please contact support", callback_data=f"quick_contact_{question_id}")],
            [InlineKeyboardButton("❓ Need more information", callback_data=f"quick_info_{question_id}")],
            [InlineKeyboardButton("💬 Custom Reply", callback_data=f"reply_{question_id}")],
            [InlineKeyboardButton("🔙 Back", callback_data=f"back_{question_id}")]
        ])
        
        await query.edit_message_text(
            text=query.message.text + "\n\n🤖 *Quick Answer Options:*",
            reply_markup=quick_answers_keyboard,
            parse_mode='Markdown'
        )
        
    elif action == "close":
        support_bot.update_question_status(question_id, "closed")
        await query.answer("✅ Question closed.")
        
        # Update the message to show it's closed
        await query.edit_message_text(
            text=query.message.text + "\n\n❌ *Question Closed*",
            parse_mode='Markdown'
        )
        
        # Notify user that question was closed
        question_data = support_bot.get_question_by_id(question_id)
        if question_data:
            _, original_user_id, username, original_question, timestamp = question_data
            try:
                await context.bot.send_message(
                    chat_id=original_user_id,
                    text=f"📝 Your question #{question_id} has been closed by our admin team.\n\n"
                         f"If you need further assistance, please send a new question.",
                    parse_mode='Markdown'
                )
            except Exception as e:
                logger.error(f"Failed to notify user about closed question: {e}")
    
    elif action.startswith("quick_"):
        # Handle quick answers
        quick_type = action.replace("quick_", "")
        quick_responses = {
            "thanks": "✅ Thank you for your question! Our team has received it and will get back to you soon.",
            "working": "⏳ Thank you for your question! We're currently working on this issue and will update you shortly.",
            "contact": "📞 Please contact our support team directly for immediate assistance with this matter.",
            "info": "❓ Thank you for your question! We need a bit more information to help you better. Please provide additional details."
        }
        
        reply_text = quick_responses.get(quick_type, "Thank you for your question!")
        
        # Send quick answer to user
        question_data = support_bot.get_question_by_id(question_id)
        if question_data:
            _, original_user_id, username, original_question, timestamp = question_data
            
            # Update question status
            support_bot.update_question_status(question_id, "answered", reply_text)
            
            try:
                await context.bot.send_message(
                    chat_id=original_user_id,
                    text=f"✅ *Your Question Has Been Answered*\n\n"
                         f"*Your Question:*\n{original_question}\n\n"
                         f"*Admin Reply:*\n{reply_text}\n\n"
                         f"*Question ID:* #{question_id}",
                    parse_mode='Markdown'
                )
                
                await query.answer("✅ Quick answer sent!")
                
                # Update the admin message
                await query.edit_message_text(
                    text=query.message.text + f"\n\n✅ *Quick Answer Sent:*\n{reply_text}",
                    parse_mode='Markdown'
                )
                
            except Exception as e:
                await query.answer(f"❌ Failed to send quick answer: {e}")
                logger.error(f"Failed to send quick answer: {e}")
    
    elif action == "back":
        # Go back to original question view
        question_data = support_bot.get_question_by_id(question_id)
        if question_data:
            _, original_user_id, username, original_question, timestamp = question_data
            
            # Recreate original keyboard
            admin_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("💬 Reply", callback_data=f"reply_{question_id}"),
                    InlineKeyboardButton("✅ Quick Answer", callback_data=f"answer_{question_id}")
                ],
                [
                    InlineKeyboardButton("❌ Close", callback_data=f"close_{question_id}"),
                    InlineKeyboardButton("📋 View All", callback_data=f"viewall")
                ]
            ])
            
            original_message = f"""
🔔 *New Question Received*

*From:* {username}
*User ID:* `{original_user_id}`
*Question ID:* #{question_id}
*Time:* {timestamp}

*Question:*
{original_question}

📝 *Instructions:*
• Click "💬 Reply" to send a custom response
• Click "✅ Quick Answer" for common responses
• Click "❌ Close" to mark as resolved
"""
            
            await query.edit_message_text(
                text=original_message,
                reply_markup=admin_keyboard,
                parse_mode='Markdown'
            )

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin replies to questions"""
    user_id = update.effective_user.id
    
    # Check if user is admin
    if not support_bot.is_admin(user_id):
        return
    
    message_text = update.message.text
    
    # Check if admin wants to cancel
    if message_text.lower() == '/cancel':
        if 'replying_question' in context.user_data:
            del context.user_data['replying_question']
            await update.message.reply_text("❌ Reply cancelled.")
        return
    
    # Check if admin is replying to a question
    question_id = None
    if 'replying_question' in context.user_data:
        question_id = context.user_data['replying_question']
    elif 'answering_question' in context.user_data:
        question_id = context.user_data['answering_question']
    
    if not question_id:
        return
    
    admin_reply = message_text
    
    # Get the original question
    question_data = support_bot.get_question_by_id(question_id)
    if not question_data:
        await update.message.reply_text("❌ Question not found.")
        return
    
    _, original_user_id, username, original_question, timestamp = question_data
    
    # Update question status
    support_bot.update_question_status(question_id, "answered", admin_reply)
    
    # Send reply to original user
    user_message = f"""
✅ *Your Question Has Been Answered*

*Your Question:*
{original_question}

*Admin Reply:*
{admin_reply}

*Question ID:* #{question_id}
*Replied on:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    try:
        await context.bot.send_message(
            chat_id=original_user_id,
            text=user_message,
            parse_mode='Markdown'
        )
        
        await update.message.reply_text(
            f"✅ *Reply Sent Successfully!*\n\n"
            f"📝 Question ID: #{question_id}\n"
            f"👤 User: {username}\n"
            f"💬 Your reply has been delivered to the user.",
            parse_mode='Markdown'
        )
        
        logger.info(f"Reply sent for question #{question_id}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Failed to send reply to user: {e}")
        logger.error(f"Failed to send reply to user: {e}")
    
    # Clear the replying/answering state
    if 'replying_question' in context.user_data:
        del context.user_data['replying_question']
    if 'answering_question' in context.user_data:
        del context.user_data['answering_question']

async def view_questions_inline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all pending questions inline"""
    user_id = update.effective_user.id
    
    if not support_bot.is_admin(user_id):
        return
    
    questions = support_bot.get_pending_questions()
    
    if not questions:
        await update.callback_query.message.reply_text("📭 No pending questions.")
        return
    
    # Create buttons for each question
    keyboard = []
    for q_id, user_id, username, question, timestamp in questions[:10]:  # Limit to 10 questions
        question_preview = question[:30] + "..." if len(question) > 30 else question
        keyboard.append([
            InlineKeyboardButton(
                f"#{q_id}: {question_preview}", 
                callback_data=f"view_question_{q_id}"
            )
        ])
    
    if len(questions) > 10:
        keyboard.append([InlineKeyboardButton("📄 View More", callback_data="view_more")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.message.reply_text(
        f"📋 *Pending Questions ({len(questions)} total)*\n\n"
        f"Select a question to view details:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def view_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all pending questions (admin only)"""
    user_id = update.effective_user.id
    
    if not support_bot.is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    questions = support_bot.get_pending_questions()
    
    if not questions:
        await update.message.reply_text("📭 No pending questions.")
        return
    
    # Create interactive buttons for each question
    keyboard = []
    for q_id, user_id, username, question, timestamp in questions[:10]:  # Limit to 10 questions
        question_preview = question[:30] + "..." if len(question) > 30 else question
        keyboard.append([
            InlineKeyboardButton(
                f"#{q_id}: {question_preview}", 
                callback_data=f"view_question_{q_id}"
            )
        ])
    
    if len(questions) > 10:
        keyboard.append([InlineKeyboardButton("📄 Show All", callback_data="show_all_questions")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"📋 *Pending Questions ({len(questions)} total)*\n\n"
        f"Click on a question to view details and reply:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def add_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add admin (use this command initially to set up admins)"""
    user = update.effective_user
    support_bot.add_admin(user.id, user.username or user.first_name)
    await update.message.reply_text(f"✅ {user.first_name} added as admin!")
    logger.info(f"Admin added: {user.first_name} (ID: {user.id})")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check bot status"""
    user_id = update.effective_user.id
    
    if not support_bot.is_admin(user_id):
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    # Get database stats
    support_bot.cursor.execute("SELECT COUNT(*) FROM questions")
    total_questions = support_bot.cursor.fetchone()[0]
    
    support_bot.cursor.execute("SELECT COUNT(*) FROM questions WHERE status = 'pending'")
    pending_questions = support_bot.cursor.fetchone()[0]
    
    support_bot.cursor.execute("SELECT COUNT(*) FROM admins")
    total_admins = support_bot.cursor.fetchone()[0]
    
    status_message = f"""
📊 *Bot Status*

*Database:* ✅ Connected
*Total Questions:* {total_questions}
*Pending Questions:* {pending_questions}
*Total Admins:* {total_admins}

*Environment:* Railway
*Status:* 🟢 Online
"""
    
    await update.message.reply_text(status_message, parse_mode='Markdown')

def main():
    """Start the bot"""
    try:
        # Create application
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("questions", view_questions))
        application.add_handler(CommandHandler("addadmin", add_admin_command))
        application.add_handler(CommandHandler("status", status_command))
        
        # Callback query handler for admin buttons
        application.add_handler(CallbackQueryHandler(handle_admin_callback))
        
        # Message handlers
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            lambda update, context: (
                handle_admin_reply(update, context) 
                if support_bot.is_admin(update.effective_user.id) and 
                   ('replying_question' in context.user_data or 'answering_question' in context.user_data)
                else handle_question(update, context)
            )
        ))
        
        # Start the bot
        logger.info("🤖 Support Bot is starting on Railway...")
        print("🤖 Support Bot is starting on Railway...")
        
        # Use webhook for Railway deployment
        PORT = int(os.environ.get('PORT', 8000))
        application.run_webhook(
            listen="0.0.0.0",
            port=PORT,
            webhook_url=f"https://{os.environ.get('RAILWAY_STATIC_URL', 'localhost')}"
        )
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        print(f"Failed to start bot: {e}")

if __name__ == '__main__':
    main()

# .gitignore
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.venv/
pip-log.txt
pip-delete-this-directory.txt
.tox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.log
.git
.mypy_cache
.pytest_cache
.hypothesis
*.db
*.sqlite3
.env
.DS_Store

# runtime.txt
python-3.11.0
