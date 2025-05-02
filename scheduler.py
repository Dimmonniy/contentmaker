import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import AUTO_SCAN_INTERVAL
from bot import publish_scheduled

scheduler = AsyncIOScheduler()

def start_scheduler():
    scheduler.add_job(lambda: asyncio.create_task(publish_scheduled()), 'interval', seconds=AUTO_SCAN_INTERVAL, id='auto_publish')
    scheduler.start()