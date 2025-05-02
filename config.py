import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")  # e.g., postgresql+asyncpg://user:pass@localhost/dbname
DEESEEK_API_URL = os.getenv("DEESEEK_API_URL")
DEESEEK_API_KEY = os.getenv("DEESEEK_API_KEY")
AUTO_SCAN_INTERVAL = int(os.getenv("AUTO_SCAN_INTERVAL", "7200"))  # seconds

# Rewrite parameters
defaults = {
    'DEFAULT_REWRITE_STYLE': os.getenv("DEFAULT_REWRITE_STYLE", "default"),
    'AVAILABLE_REWRITE_STYLES': os.getenv("AVAILABLE_REWRITE_STYLES", "default,formal,casual").split(",")
}
DEFAULT_REWRITE_STYLE = defaults['DEFAULT_REWRITE_STYLE']
AVAILABLE_REWRITE_STYLES = defaults['AVAILABLE_REWRITE_STYLES']