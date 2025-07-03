import os
import logging
import json
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# إعداد السجلات
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# التوكن الخاص بك
BOT_TOKEN = os.environ.get('BOT_TOKEN') or "7910999203:AAFEmX2G-q4vw8Mtf8JJ-x1TSCsNzn09Ch4"

# معرف الأدمن (ضع معرفك هنا)
ADMIN_ID = int(os.environ.get('ADMIN_ID', '8011237487')) or "8011237487"

# قاموس لحفظ الأسئلة المعلقة
pending_questions = {}
question_counter = 1

# دالة لتحديث عداد الأسئلة بناءً على الأسئلة الموجودة
def update_question_counter():
    global question_counter
    if pending_questions:
        # استخراج جميع أرقام الأسئلة الموجودة
        existing_numbers = []
        for q_id in pending_questions.keys():
            if q_id.startswith('Q') and q_id[1:].isdigit():
                existing_numbers.append(int(q_id[1:]))
        
        if existing_numbers:
            question_counter = max(existing_numbers) + 1
        else:
            question_counter = 1
    else:
        question_counter = 1

# دالة لحفظ البيانات (في الذاكرة فقط)
def save_question(user_id, username, question, question_id):
    global pending_questions
    pending_questions[question_id] = {
        'user_id': user_id,
        'username': username,
        'question': question,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'pending'
    }

# دالة البداية للمستخدمين العاديين
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id == ADMIN_ID:
        await update.message.reply_text(
            f"مرحباً بك يا أدمن! 👨‍💼\n\n"
            "أنت الآن في وضع الإدارة. ستتلقى جميع الأسئلة هنا.\n\n"
            "الأوامر المتاحة:\n"
            "/pending - عرض الأسئلة المعلقة\n"
            "/stats - إحصائيات البوت\n"
            "/help - المساعدة\n"
            "/reset_counter - إعادة تعيين عداد الأسئلة"
        )
    else:
        await update.message.reply_text(
            f"مرحباً {user.first_name}! 👋\n\n"
            "أنا بوت الأسئلة والأجوبة 🤖\n\n"
            "يمكنك إرسال أي سؤال لي وسأقوم بتوصيله للمختص،\n"
            "وبمجرد الإجابة عليه ستتلقى الرد! 📩\n\n"
            "فقط اكتب سؤالك واضغط إرسال 📝"
        )

# دالة استقبال الأسئلة
async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global question_counter
    
    user = update.effective_user
    question = update.message.text
    
    # إذا كان المرسل هو الأدمن
    if user.id == ADMIN_ID:
        await handle_admin_response(update, context)
        return
    
    # تحديث عداد الأسئلة
    update_question_counter()
    
    # حفظ السؤال
    question_id = f"Q{question_counter}"
    save_question(user.id, user.username or user.first_name, question, question_id)
    question_counter += 1
    
    # إرسال تأكيد للمستخدم
    await update.message.reply_text(
        f"✅ تم استلام سؤالك!\n\n"
        f"🆔 رقم السؤال: {question_id}\n"
        f"⏰ الوقت: {datetime.now().strftime('%H:%M')}\n\n"
        f"سيتم الرد عليك في أقرب وقت ممكن! 🕐"
    )
    
    # إرسال السؤال للأدمن
    if ADMIN_ID > 0:
        admin_message = f"📩 *سؤال جديد!*\n\n"
        admin_message += f"🆔 رقم السؤال: `{question_id}`\n"
        admin_message += f"👤 من: {user.first_name}"
        if user.username:
            admin_message += f" (@{user.username})"
        admin_message += f"\n🆔 المعرف: `{user.id}`\n"
        admin_message += f"⏰ الوقت: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        admin_message += f"❓ السؤال:\n{question}\n\n"
        admin_message += f"📝 للرد: اكتب `{question_id}` ثم الإجابة"
        
        # إضافة أزرار سريعة
        keyboard = [
            [InlineKeyboardButton("✅ تم الرد", callback_data=f"answered_{question_id}")],
            [InlineKeyboardButton("❌ حذف السؤال", callback_data=f"delete_{question_id}")],
            [InlineKeyboardButton("👤 معلومات المستخدم", callback_data=f"info_{user.id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_message,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"خطأ في إرسال الرسالة للأدمن: {e}")

# دالة معالجة ردود الأدمن
async def handle_admin_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    
    # البحث عن رقم السؤال في بداية الرسالة
    if message.startswith('Q') and ' ' in message:
        parts = message.split(' ', 1)
        question_id = parts[0]
        answer = parts[1]
        
        # التحقق من وجود السؤال
        if question_id in pending_questions:
            question_data = pending_questions[question_id]
            user_id = question_data['user_id']
            original_question = question_data['question']
            
            # إرسال الإجابة للمستخدم
            user_message = f"✅ *تم الرد على سؤالك!*\n\n"
            user_message += f"🆔 رقم السؤال: {question_id}\n"
            user_message += f"❓ سؤالك كان:\n{original_question}\n\n"
            user_message += f"💬 الإجابة:\n{answer}\n\n"
            user_message += f"⏰ وقت الرد: {datetime.now().strftime('%H:%M')}"
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=user_message,
                    parse_mode='Markdown'
                )
                
                # تحديث حالة السؤال
                pending_questions[question_id]['status'] = 'answered'
                pending_questions[question_id]['answer'] = answer
                pending_questions[question_id]['answered_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # تأكيد للأدمن
                await update.message.reply_text(
                    f"✅ تم إرسال الإجابة بنجاح!\n\n"
                    f"🆔 السؤال: {question_id}\n"
                    f"👤 إلى: {question_data['username']}"
                )
                
            except Exception as e:
                await update.message.reply_text(
                    f"❌ خطأ في إرسال الإجابة:\n{str(e)}\n\n"
                    f"قد يكون المستخدم حظر البوت أو حذف المحادثة."
                )
        else:
            # البحث في جميع الأسئلة حتى لو لم تكن معلقة
            found = False
            for q_id, q_data in pending_questions.items():
                if q_id == question_id:
                    found = True
                    if q_data['status'] == 'answered':
                        await update.message.reply_text(
                            f"⚠️ السؤال {question_id} تم الرد عليه مسبقاً!\n\n"
                            f"الإجابة السابقة: {q_data.get('answer', 'غير متوفرة')}\n"
                            f"وقت الرد: {q_data.get('answered_at', 'غير متوفر')}"
                        )
                    break
            
            if not found:
                await update.message.reply_text(
                    f"❌ لم يتم العثور على السؤال: {question_id}\n\n"
                    f"الأسئلة المتاحة:\n"
                    f"{', '.join(list(pending_questions.keys())[-10:])}\n\n"
                    f"استخدم /pending لرؤية الأسئلة المعلقة\n"
                    f"أو /all_questions لرؤية جميع الأسئلة"
                )
    else:
        await update.message.reply_text(
            "📝 تنسيق الرد:\n"
            "`Q[رقم_السؤال] هنا الإجابة على السؤال`\n\n"
            "مثال:\n"
            "`Q1 هذه إجابة سؤالك`\n"
            "`Q15 إجابة السؤال رقم 15`\n\n"
            "استخدم /pending لرؤية الأسئلة المعلقة"
        )

# دالة عرض الأسئلة المعلقة
async def show_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ هذا الأمر للأدمن فقط!")
        return
    
    pending = {q_id: q_data for q_id, q_data in pending_questions.items() if q_data['status'] == 'pending'}
    
    if not pending:
        await update.message.reply_text("✅ لا توجد أسئلة معلقة!")
        return
    
    message = f"📋 *الأسئلة المعلقة ({len(pending)}):*\n\n"
    
    # ترتيب الأسئلة حسب الرقم
    sorted_questions = sorted(pending.items(), key=lambda x: int(x[0][1:]) if x[0][1:].isdigit() else 0)
    
    for q_id, data in sorted_questions:
        message += f"🆔 `{q_id}` - {data['username']}\n"
        message += f"⏰ {data['timestamp']}\n"
        message += f"❓ {data['question'][:50]}{'...' if len(data['question']) > 50 else ''}\n\n"
    
    # تقسيم الرسالة إذا كانت طويلة
    if len(message) > 4000:
        parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
        for part in parts:
            await update.message.reply_text(part, parse_mode='Markdown')
    else:
        await update.message.reply_text(message, parse_mode='Markdown')

# دالة عرض جميع الأسئلة
async def show_all_questions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ هذا الأمر للأدمن فقط!")
        return
    
    if not pending_questions:
        await update.message.reply_text("📭 لا توجد أسئلة!")
        return
    
    message = f"📋 *جميع الأسئلة ({len(pending_questions)}):*\n\n"
    
    # ترتيب الأسئلة حسب الرقم
    sorted_questions = sorted(pending_questions.items(), key=lambda x: int(x[0][1:]) if x[0][1:].isdigit() else 0)
    
    for q_id, data in sorted_questions:
        status_emoji = "✅" if data['status'] == 'answered' else "⏳"
        message += f"{status_emoji} `{q_id}` - {data['username']}\n"
        message += f"⏰ {data['timestamp']}\n"
        if data['status'] == 'answered':
            message += f"📅 أُجيب في: {data.get('answered_at', 'غير متوفر')}\n"
        message += "\n"
    
    # تقسيم الرسالة إذا كانت طويلة
    if len(message) > 4000:
        parts = [message[i:i+4000] for i in range(0, len(message), 4000)]
        for part in parts:
            await update.message.reply_text(part, parse_mode='Markdown')
    else:
        await update.message.reply_text(message, parse_mode='Markdown')

# دالة الإحصائيات
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ هذا الأمر للأدمن فقط!")
        return
    
    total = len(pending_questions)
    answered = len([q for q in pending_questions.values() if q['status'] == 'answered'])
    pending = len([q for q in pending_questions.values() if q['status'] == 'pending'])
    
    stats_message = f"📊 *إحصائيات البوت:*\n\n"
    stats_message += f"📝 إجمالي الأسئلة: {total}\n"
    stats_message += f"✅ تم الرد عليها: {answered}\n"
    stats_message += f"⏳ في الانتظار: {pending}\n"
    stats_message += f"📈 معدل الإجابة: {(answered/total*100):.1f}%" if total > 0 else "📈 معدل الإجابة: 0%"
    stats_message += f"\n🔢 آخر رقم سؤال: Q{question_counter-1}" if question_counter > 1 else "\n🔢 لم يتم إنشاء أسئلة بعد"
    
    await update.message.reply_text(stats_message, parse_mode='Markdown')

# دالة إعادة تعيين عداد الأسئلة
async def reset_counter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ هذا الأمر للأدمن فقط!")
        return
    
    global question_counter
    update_question_counter()
    
    await update.message.reply_text(
        f"🔄 تم تحديث عداد الأسئلة!\n\n"
        f"العداد الحالي: {question_counter}\n"
        f"السؤال التالي سيكون: Q{question_counter}"
    )

# دالة معالجة الأزرار
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.edit_message_text("❌ غير مسموح!")
        return
    
    data = query.data
    
    if data.startswith('answered_'):
        question_id = data.split('_')[1]
        if question_id in pending_questions:
            pending_questions[question_id]['status'] = 'answered'
            pending_questions[question_id]['answered_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            await query.edit_message_text(
                f"✅ تم تحديد السؤال {question_id} كمُجاب عليه"
            )
    
    elif data.startswith('delete_'):
        question_id = data.split('_')[1]
        if question_id in pending_questions:
            del pending_questions[question_id]
            await query.edit_message_text(
                f"🗑️ تم حذف السؤال {question_id}"
            )
    
    elif data.startswith('info_'):
        user_id = data.split('_')[1]
        user_questions = [q for q in pending_questions.values() if str(q['user_id']) == user_id]
        
        info_message = f"👤 *معلومات المستخدم:*\n\n"
        info_message += f"🆔 المعرف: `{user_id}`\n"
        info_message += f"📝 عدد الأسئلة: {len(user_questions)}\n"
        
        if user_questions:
            info_message += f"🕐 آخر سؤال: {user_questions[-1]['timestamp']}"
        
        await query.edit_message_text(info_message, parse_mode='Markdown')

# دالة المساعدة للأدمن
async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ هذا الأمر للأدمن فقط!")
        return
    
    help_text = """
🔧 *أوامر الأدمن:*

📋 `/pending` - عرض الأسئلة المعلقة
📊 `/stats` - إحصائيات البوت
📝 `/all_questions` - جميع الأسئلة
🔄 `/reset_counter` - تحديث عداد الأسئلة
❓ `/help` - هذه المساعدة

📝 *طريقة الرد على الأسئلة:*
`Q[رقم_السؤال] هنا الإجابة`

أمثلة:
`Q1 مرحباً، إجابة سؤالك هي...`
`Q15 إجابة السؤال رقم 15`
`Q100 إجابة السؤال رقم 100`

💡 *نصائح:*
• استخدم الأزرار للإجراءات السريعة
• يمكنك نسخ رقم السؤال من الرسالة
• البوت يحفظ تاريخ كل سؤال وإجابة
• استخدم /reset_counter لتحديث العداد بعد إعادة التشغيل
    """
    
    await update.message.reply_text(help_text, parse_mode='Markdown')

# دالة معالجة الأخطاء
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Exception while handling an update:", exc_info=context.error)

def main():
    if not BOT_TOKEN or BOT_TOKEN == "ضع_التوكن_هنا":
        print("❌ خطأ: يجب إضافة BOT_TOKEN")
        return
    
    if not ADMIN_ID or ADMIN_ID == 0:
        print("⚠️ تحذير: يجب إضافة ADMIN_ID لتلقي الأسئلة")
        print("لمعرفة معرفك، أرسل رسالة لبوت @userinfobot")
    
    # تحديث عداد الأسئلة عند بدء التشغيل
    update_question_counter()
    
    # إنشاء التطبيق
    app = Application.builder().token(BOT_TOKEN).build()
    
    # إضافة معالجات الأوامر
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pending", show_pending))
    app.add_handler(CommandHandler("stats", show_stats))
    app.add_handler(CommandHandler("help", admin_help))
    app.add_handler(CommandHandler("all_questions", show_all_questions))
    app.add_handler(CommandHandler("reset_counter", reset_counter))
    
    # معالج الأزرار
    app.add_handler(CallbackQueryHandler(button_handler))
    
    # معالج الرسائل النصية
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))
    
    # معالج الأخطاء
    app.add_error_handler(error_handler)
    
    # تشغيل البوت
    print("🚀 بوت الأسئلة والأجوبة يعمل الآن...")
    print(f"📧 معرف الأدمن: {ADMIN_ID}")
    print(f"🔢 عداد الأسئلة: {question_counter}")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
