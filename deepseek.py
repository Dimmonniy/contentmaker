import aiohttp
from config import DEESEEK_API_URL, DEESEEK_API_KEY, DEFAULT_REWRITE_STYLE

_session = None

async def get_session():
    global _session
    if _session is None:
        _session = aiohttp.ClientSession()
    return _session

async def rewrite_text(text: str, style: str = None) -> str:
    style_to_use = style or DEFAULT_REWRITE_STYLE
    payload = { 'api_key': DEESEEK_API_KEY, 'text': text, 'style': style_to_use }
    sess = await get_session()
    async with sess.post(f"{DEESEEK_API_URL}/rewrite", json=payload) as resp:
        resp.raise_for_status()
        data = await resp.json()
        return data.get('rewritten_text', text)