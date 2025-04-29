import os
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any

from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackContext,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    ConversationHandler
)
from apscheduler.schedulers.background import BackgroundScheduler
import requests
from bs4 import BeautifulSoup

# Загрузка конфигурации
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
USER_ID = int(os.getenv('USER_ID'))
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')

# Инициализация логгера
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
SELECTING_ACTION, EDITING_TEXT, SCHEDULING = range(3)

class ContentMakerBot:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.scheduler.start()
        self.init_db()
        self.setup_handlers()
        self.setup_scheduled_jobs()

    def init_db(self):
        self.conn = sqlite3.connect('contentmaker.db')
        
    def setup_handlers(self):
        self.updater = Updater(TOKEN, use_context=True)
        dp = self.updater.dispatcher

        # Основные команды
        dp.add_handler(CommandHandler('start', self.start))
        dp.add_handler(CommandHandler('new_block', self.new_block))
        dp.add_handler(CommandHandler('add_channel', self.add_channel))
        dp.add_handler(CommandHandler('parse_now', self.parse_now))
        
        # Модерация
        dp.add_handler(ConversationHandler(
            entry_points=[CommandHandler('moderate', self.moderate)],
            states={
                SELECTING_ACTION: [CallbackQueryHandler(self.handle_moderation_action)],
                EDITING_TEXT: [MessageHandler(Filters.text & ~Filters.command, self.save_edited_text)]
            },
            fallbacks=[]
        ))

        # Публикация
        dp.add_handler(CommandHandler('publish', self.publish))
        dp.add_handler(CallbackQueryHandler(self.handle_scheduling))

        # Медиа
        dp.add_handler(MessageHandler(
            Filters.photo | Filters.video | Filters.document,
            self.handle_media
        ))

    def setup_scheduled_jobs(self):
        self.scheduler.add_job(
            self.check_scheduled_posts,
            'interval',
            minutes=5,
            next_run_time=datetime.now()
        )

    # Основные команды
    def start(self, update: Update, context: CallbackContext):
        if update.effective_user.id != USER_ID:
            return
        update.message.reply_text("🚀 Бот-контентмейкер активирован!")

    def new_block(self, update: Update, context: CallbackContext):
        update.message.reply_text("Введите название тематического блока:")
        return 'waiting_block_name'

    # Парсинг каналов
    def parse_channel(self, username: str) -> list:
        url = f"https://t.me/s/{username}"
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            return [
                msg.select_one('.tgme_widget_message_text').get_text(separator='\n')
                for msg in soup.select('.tgme_widget_message')
                if msg.select_one('.tgme_widget_message_text')
            ]
        except Exception as e:
            logger.error(f"Ошибка парсинга: {str(e)}")
            return []

    # Рерайтинг через DeepSeek
    def rewrite_text(self, text: str) -> str:
        headers = {'Authorization': f'Bearer {DEEPSEEK_API_KEY}'}
        try:
            response = requests.post(
                'https://api.deepseek.com/v1/rewrite',
                headers=headers,
                json={'text': text, 'style': 'professional'}
            )
            return response.json().get('rewritten_text', text)
        except Exception as e:
            logger.error(f"Ошибка DeepSeek: {str(e)}")
            return text

    # Модерация
    def moderate(self, update: Update, context: CallbackContext):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, rewritten_text FROM messages WHERE status = 'pending'")
        messages = cursor.fetchall()
        
        keyboard = [
            [InlineKeyboardButton(f"✏️ Редактировать {msg[0]}", callback_data=f"edit_{msg[0]}")]
            for msg in messages
        ]
        update.message.reply_text(
            "Очередь модерации:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return SELECTING_ACTION

    # Публикация
    def publish(self, update: Update, context: CallbackContext):
        keyboard = [
            [InlineKeyboardButton("Сейчас", callback_data="now")],
            [InlineKeyboardButton("Запланировать", callback_data="schedule")]
        ]
        update.message.reply_text(
            "Выберите время публикации:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def check_scheduled_posts(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM publication_queue 
            WHERE scheduled_time <= datetime('now') 
            AND is_published = 0
        ''')
        for post in cursor.fetchall():
            self.send_to_channel(post[1])
            cursor.execute('UPDATE publication_queue SET is_published = 1 WHERE id = ?', (post[0],))
        self.conn.commit()

    def send_to_channel(self, message_id: int):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT rewritten_text, media_type, media_id 
            FROM messages 
            WHERE id = ?
        ''', (message_id,))
        text, media_type, media_id = cursor.fetchone()
        
        # Здесь должна быть логика отправки в ваш канал
        logger.info(f"PUBLISHED: {text}")

    def run(self):
        self.updater.start_polling()
        self.updater.idle()

if __name__ == '__main__':
    bot = ContentMakerBot()
    bot.run()