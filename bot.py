import logging
import asyncio
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardButton, InlineKeyboardMarkup,
    InputMediaPhoto
)
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config import (
    BOT_TOKEN,
    AVAILABLE_REWRITE_STYLES,
    DEFAULT_REWRITE_STYLE,
    AUTO_SCAN_INTERVAL
)
from models import (
    AsyncSessionLocal, init_db,
    ThemeBlock, Channel, BotConfig,
    Message as MsgModel, RewriteTask,
    ModerationTask, PublicationSchedule
)
from deepseek import rewrite_text
from publisher import publish_message
from scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# FSM for moderation states
class ModerationStates(StatesGroup):
    editing_text = State()
    adding_media = State()

# Configuration helpers
async def get_conf(key: str):
    async with AsyncSessionLocal() as session:
        cfg = await session.get(BotConfig, key)
        return cfg.value if cfg else None

async def set_conf(key: str, value: str):
    async with AsyncSessionLocal() as session:
        cfg = await session.get(BotConfig, key)
        if cfg:
            cfg.value = value
        else:
            session.add(BotConfig(key=key, value=value))
        await session.commit()

# /set_channel and /get_channel
@dp.message(Command("set_channel"))
async def cmd_set_channel(msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.reply("Использование: /set_channel <@username|chat_id>")
        return
    await set_conf('TARGET_CHAT_ID', parts[1])
    await msg.reply(f"Канал для публикации установлен: {parts[1]}")

@dp.message(Command("get_channel"))
async def cmd_get_channel(msg: Message):
    target = await get_conf('TARGET_CHAT_ID') or 'не задан'
    style = await get_conf('DEFAULT_REWRITE_STYLE') or DEFAULT_REWRITE_STYLE
    await msg.reply(
        f"Текущий канал: {target}
"
        f"Текущий стиль рерайта: {style}"
    )

# /set_style
@dp.message(Command("set_style"))
async def cmd_set_style(msg: Message):
    parts = msg.text.split(maxsplit=1)
    choices = ", ".join(AVAILABLE_REWRITE_STYLES)
    if len(parts) < 2 or parts[1] not in AVAILABLE_REWRITE_STYLES:
        await msg.reply(
            f"Использование: /set_style <style>
"
            f"Доступные стили: {choices}"
        )
        return
    await set_conf('DEFAULT_REWRITE_STYLE', parts[1])
    await msg.reply(f"Стиль рерайта установлен: {parts[1]}")

# CRUD blocks
@dp.message(Command("add_block"))
async def cmd_add_block(msg: Message):
    title = msg.text.partition(' ')[2].strip()
    if not title:
        await msg.reply("Использование: /add_block <название>")
        return
    async with AsyncSessionLocal() as session:
        block = ThemeBlock(title=title)
        session.add(block)
        await session.commit()
        await msg.reply(f"Создан блок '{title}' (id={block.id})")

@dp.message(Command("list_blocks"))
async def cmd_list_blocks(msg: Message):
    async with AsyncSessionLocal() as session:
        res = await session.execute(ThemeBlock.__table__.select())
        blocks = res.scalars().all()
    if not blocks:
        await msg.reply("Список блоков пуст.")
        return
    text = "
".join(f"{b.id}: {b.title}" for b in blocks)
    await msg.reply(f"Список блоков:
{text}")

@dp.message(Command("remove_block"))
async def cmd_remove_block(msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        await msg.reply("Использование: /remove_block <block_id>")
        return
    block_id = int(parts[1])
    async with AsyncSessionLocal() as session:
        block = await session.get(ThemeBlock, block_id)
        if not block:
            await msg.reply("Блок не найден.")
            return
        await session.delete(block)
        await session.commit()
        await msg.reply(f"Удалён блок id={block_id}")

# CRUD channels
@dp.message(Command("add_channel"))
async def cmd_add_channel(msg: Message):
    parts = msg.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await msg.reply("Использование: /add_channel <block_id> @username")
        return
    block_id, username = int(parts[1]), parts[2]
    async with AsyncSessionLocal() as session:
        ch = Channel(block_id=block_id, username=username)
        session.add(ch)
        await session.commit()
        await msg.reply(f"Добавлен канал {username} в блок {block_id}")

@dp.message(Command("list_channels"))
async def cmd_list_channels(msg: Message):
    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].isdigit():
        await msg.reply("Использование: /list_channels <block_id>")
        return
    block_id = int(parts[1])
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            Channel.__table__.select().where(Channel.block_id == block_id)
        )
        channels = res.scalars().all()
    if not channels:
        await msg.reply("В блоке нет каналов.")
        return
    text = "
".join(f"{c.id}: {c.username}" for c in channels)
    await msg.reply(f"Каналы в блоке {block_id}:
{text}")

@dp.message(Command("remove_channel"))
async def cmd_remove_channel(msg: Message):
    parts = msg.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await msg.reply("Использование: /remove_channel <block_id> @username")
        return
    block_id, username = int(parts[1]), parts[2]
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            Channel.__table__.select().where(
                Channel.block_id == block_id,
                Channel.username == username
            )
        )
        ch = res.scalars().first()
        if not ch:
            await msg.reply("Канал не найден.")
            return
        await session.delete(ch)
        await session.commit()
        await msg.reply(f"Удалён канал {username} из блока {block_id}")

# Message scan stub
async def scan_block(block_id: int, hours: int):
    return []  # TODO implement

@dp.message(Command("scan"))
async def cmd_scan(msg: Message):
    parts = msg.text.split()
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await msg.reply("Использование: /scan <block_id> <hours>")
        return
    block_id, hours = int(parts[1]), int(parts[2])
    msgs = await scan_block(block_id, hours)
    await msg.reply(f"Собрано {len(msgs)} сообщений")

# Rewrite funnel
@dp.message(Command("select_for_rewrite"))
async def cmd_select_for_rewrite(msg: Message):
    parts = msg.text.split()
    usage = (f"Использование: /select_for_rewrite <block_id> [style]
"
             f"Стили: {', '.join(AVAILABLE_REWRITE_STYLES)}")
    if len(parts) < 2 or not parts[1].isdigit():
        await msg.reply(usage)
        return
    block_id = int(parts[1])
    user_style = parts[2] if len(parts) > 2 else None
    async with AsyncSessionLocal() as session:
        style = (user_style if user_style in AVAILABLE_REWRITE_STYLES
                 else await get_conf('DEFAULT_REWRITE_STYLE') or DEFAULT_REWRITE_STYLE)
        res = await session.execute(
            Channel.__table__.select().where(Channel.block_id == block_id)
        )
        channel_ids = [c.id for c in res.scalars().all()]
        res = await session.execute(
            MsgModel.__table__.select().where(
                MsgModel.status == 'new',
                MsgModel.channel_id.in_(channel_ids)
            )
        )
        msgs = res.scalars().all()
    if not msgs:
        await msg.reply("Нет новых сообщений.")
        return
    kb = InlineKeyboardMarkup()
    for m in msgs:
        snippet = (m.content or '')[:30].replace('
',' ') + '...'
        kb.add(InlineKeyboardButton(f"[{style}] {snippet}", callback_data=f"rewrite:{m.id}:{style}"))
    await msg.reply("Выберите сообщение:", reply_markup=kb)

@dp.callback_query(F.data.startswith("rewrite:"))
async def callback_rewrite(cb: CallbackQuery):
    _, mid, style = cb.data.split(":")
    mid = int(mid)
    async with AsyncSessionLocal() as session:
        orig = await session.get(MsgModel, mid)
        new_text = await rewrite_text(orig.content, style)
        task = RewriteTask(message_id=mid, style=style, result=new_text, status='done')
        orig.status = 'funnel'
        session.add_all([orig, task])
        await session.commit()
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("Одобрить", callback_data=f"mod_approve:{task.id}"),
        InlineKeyboardButton("Редактировать", callback_data=f"mod_edit:{task.id}"),
        InlineKeyboardButton("Удалить", callback_data=f"mod_delete:{task.id}")
    )
    await cb.message.edit_text(f"Рерайт [{style}]:
{new_text}", reply_markup=kb)
    await cb.answer()

# Moderation approve/delete/edit
@dp.callback_query(F.data.startswith("mod_approve:"))
async def callback_mod_approve(cb: CallbackQuery):
    tid = int(cb.data.split(":")[1])
    async with AsyncSessionLocal() as session:
        rewrite = await session.get(RewriteTask, tid)
        mod = ModerationTask(rewrite_id=tid, user_text=rewrite.result, status='approved')
        session.add(mod)
        await session.commit()
        sched = PublicationSchedule(moderation_task_id=mod.id, scheduled_time=datetime.utcnow()+timedelta(minutes=1))
        session.add(sched)
        await session.commit()
    await cb.message.delete_reply_markup()
    await cb.answer("Сообщение запланировано.")

@dp.callback_query(F.data.startswith("mod_delete:"))
async def callback_mod_delete(cb: CallbackQuery):
    tid = int(cb.data.split(":")[1])
    async with AsyncSessionLocal() as session:
        rewrite = await session.get(RewriteTask, tid)
        await session.delete(rewrite)
        await session.commit()
    await cb.message.delete()
    await cb.answer("Удалено.")

@dp.callback_query(F.data.startswith("mod_edit:"))
async def callback_mod_edit(cb: CallbackQuery, state: FSMContext):
    tid = int(cb.data.split(":")[1])
    await state.update_data(edit_task_id=tid)
    await cb.message.reply("Отправьте новый текст:")
    await state.set_state(ModerationStates.editing_text)
    await cb.answer()

@dp.message(F.state(ModerationStates.editing_text))
async def process_edit_text(msg: Message, state: FSMContext):
    data = await state.get_data()
    tid = data.get("edit_task_id")
    async with AsyncSessionLocal() as session:
        mod = ModerationTask(rewrite_id=tid, user_text=msg.text, status='pending')
        session.add(mod)
        await session.commit()
    await msg.reply("Текст обновлён, прикрепите медиа или /skip_media")
    await state.set_state(ModerationStates.adding_media)

@dp.message(F.photo | F.video, F.state(ModerationStates.adding_media))
async def process_media(msg: Message, state: FSMContext):
    data = await state.get_data()
    tid = data.get("edit_task_id")
    file_id = msg.photo[-1].file_id if msg.photo else msg.video.file_id
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            ModerationTask.__table__.select().where(
                ModerationTask.rewrite_id==tid,
                ModerationTask.status=='pending'
            )
        )
        mt = res.scalars().first()
        if mt:
            mt.media = file_id
            await session.commit()
    await msg.reply("Медиа прикреплено.")
    await state.clear()

@dp.message(Command("skip_media"), F.state(ModerationStates.adding_media))
async def skip_media(msg: Message, state: FSMContext):
    await msg.reply("Пропускаем медиа.")
    await state.clear()

# Instant publication
@dp.message(Command("post_now"))
async def cmd_post_now(msg: Message):
    text = msg.text.partition(' ')[2].strip()
    if not text:
        await msg.reply("Использование: /post_now <текст>")
        return
    target = await get_conf('TARGET_CHAT_ID')
    if not target:
        await msg.reply("Сначала /set_channel")
        return
    await publish_message(target, text, [])
    await msg.reply("Опубликовано.")

# Show schedule
@dp.message(Command("show_schedule"))
async def cmd_show_schedule(msg: Message):
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            PublicationSchedule.__table__.select().where(PublicationSchedule.status=='scheduled')
        )
        scheds = res.scalars().all()
    if not scheds:
        await msg.reply("Расписание пусто.")
        return
    text = "
".join(f"{s.id}: task {s.moderation_task_id} @ {s.scheduled_time}" for s in scheds)
    await msg.reply(f"Расписание публикаций:
{text}")

# Scheduled publishing job
async def publish_scheduled():
    async with AsyncSessionLocal() as session:
        now = datetime.utcnow()
        res = await session.execute(
            PublicationSchedule.__table__.select().where(
                PublicationSchedule.status=='scheduled',
                PublicationSchedule.scheduled_time<=now
            )
        )
        tasks = res.scalars().all()
        target = await get_conf('TARGET_CHAT_ID')
        for s in tasks:
            mt = await session.get(ModerationTask, s.moderation_task_id)
            medias = []
            if mt.media:
                medias.append(InputMediaPhoto(mt.media))
            await publish_message(target, mt.user_text, medias)
            s.status = 'published'
        await session.commit()

# Startup
async def main():
    await init_db()
    start_scheduler()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())