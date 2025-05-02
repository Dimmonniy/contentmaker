from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

Base = declarative_base()

class ThemeBlock(Base):
    __tablename__ = 'theme_blocks'
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    channels = relationship('Channel', back_populates='block', cascade='all, delete')

class Channel(Base):
    __tablename__ = 'channels'
    id = Column(Integer, primary_key=True)
    block_id = Column(Integer, ForeignKey('theme_blocks.id', ondelete='CASCADE'))
    username = Column(String, nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    block = relationship('ThemeBlock', back_populates='channels')
    __table_args__ = (UniqueConstraint('block_id', 'username', name='_block_channel_uc'),)

class Message(Base):
    __tablename__ = 'messages'
    id = Column(Integer, primary_key=True)
    channel_id = Column(Integer, ForeignKey('channels.id'), nullable=False)
    original_message_id = Column(Integer, nullable=False)
    content = Column(Text)
    timestamp = Column(DateTime)
    status = Column(String, default='new')

class BotConfig(Base):
    __tablename__ = 'bot_config'
    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)

class RewriteTask(Base):
    __tablename__ = 'rewrite_tasks'
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey('messages.id'), nullable=False)
    style = Column(String, nullable=False)
    result = Column(Text, nullable=False)
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)

class ModerationTask(Base):
    __tablename__ = 'moderation_tasks'
    id = Column(Integer, primary_key=True)
    rewrite_id = Column(Integer, ForeignKey('rewrite_tasks.id'), nullable=False)
    user_text = Column(Text, nullable=False)
    media = Column(Text)  # JSON or Telegram file_id
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)

class PublicationSchedule(Base):
    __tablename__ = 'publication_schedule'
    id = Column(Integer, primary_key=True)
    moderation_task_id = Column(Integer, ForeignKey('moderation_tasks.id'), nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    status = Column(String, default='scheduled')
    created_at = Column(DateTime, default=datetime.utcnow)

# Async engine & session
engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)