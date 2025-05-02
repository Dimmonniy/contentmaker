from aiogram import Bot
from config import BOT_TOKEN

bot = Bot(token=BOT_TOKEN, parse_mode='HTML')

async def publish_message(chat_id: int, text: str, medias: list = None):
    if medias:
        await bot.send_media_group(chat_id, medias)
    if text:
        await bot.send_message(chat_id, text)