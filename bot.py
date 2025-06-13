import logging
import asyncio
import aiohttp
import os
import threading
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn

load_dotenv()
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
PRICE_DIFF_THRESHOLD = float(os.getenv("PRICE_DIFF_THRESHOLD", 0.001))

PAIRS = [
    "TRXUSDT", "TRXUSDC", "TRXWETH", "TRXBTT", "TRXJST",
    "TRXSUN", "TRXUSDD", "TRXFLUX", "BTCTUSDT", "TRXBTCT",
    "BTCUSDT", "ETHUSDT", "ETHTRX", "BTCTRX", "WETHUSDT",
    "USDCUSDT", "USDCWETH", "USDTBTT", "USDTJST", "USDTSUN"
]

EXCHANGES = {
    "Binance": lambda pair: f"https://api.binance.com/api/v3/ticker/price?symbol={pair}",
    "KuCoin": lambda pair: f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={pair[:3]}-{pair[3:]}",
    "MEXC": lambda pair: f"https://www.mexc.com/open/api/v2/market/ticker?symbol={pair[:3]}_{pair[3:]}",
    "OKX": lambda pair: f"https://www.okx.com/api/v5/market/ticker?instId={pair[:3]}-{pair[3:]}",
    "Bybit": lambda pair: f"https://api.bybit.com/v2/public/tickers?symbol={pair}"
}

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
scheduler = AsyncIOScheduler()
app = FastAPI()
log_messages = []
is_paused = False

logging.basicConfig(level=logging.INFO)

@app.get("/")
def root():
    return {"status": "Bot is running"}

async def fetch_price(exchange, pair):
    url = EXCHANGES[exchange](pair)
    headers = {"User-Agent": "Mozilla/5.0"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 403:
                    return None
                data = await resp.json()
                if exchange == "Binance":
                    return float(data["price"])
                elif exchange == "KuCoin":
                    return float(data["data"]["price"])
                elif exchange == "MEXC":
                    return float(data["data"][0]["last"])
                elif exchange == "OKX":
                    return float(data["data"][0]["last"])
                elif exchange == "Bybit":
                    return float(data["result"][0]["last_price"])
        except Exception:
            return None

async def check_arbitrage():
    if is_paused:
        return
    for pair in PAIRS:
        debug_message = f"🔍 <b>Отладка {pair[:3]}/{pair[3:]}:</b>\n"
        prices = {}
        for exchange in EXCHANGES:
            try:
                price = await fetch_price(exchange, pair)
                if price:
                    prices[exchange] = price
                    debug_message += f"{exchange}: {price:.5f}\n"
                else:
                    debug_message += f"{exchange}: ❌\n"
            except Exception as e:
                debug_message += f"{exchange}: ❌ ({str(e)})\n"
        log_messages.append(debug_message)
        if len(prices) >= 2:
            exs = list(prices.keys())
            p1, p2 = prices[exs[0]], prices[exs[1]]
            diff = abs(p1 - p2) / min(p1, p2)
            debug_message += f"\n<b>Diff:</b> {diff*100:.2f}%\n"
            if diff >= PRICE_DIFF_THRESHOLD:
                debug_message += "⚠️ <b>Разница превышает порог!</b>\n"
        await bot.send_message(CHAT_ID, debug_message)

@dp.message(F.text == "/start")
async def cmd_start(msg: Message):
    if msg.chat.id == CHAT_ID:
        await msg.answer("🤖 Бот готов. Введите /help для команд.")

@dp.message(F.text == "/help")
async def cmd_help(msg: Message):
    if msg.chat.id == CHAT_ID:
        await msg.answer("""🛠 Команды:
/ping
/status
/pause
/resume
/threshold 0.002
/list
/log""")

@dp.message(F.text == "/ping")
async def cmd_ping(msg: Message):
    if msg.chat.id == CHAT_ID:
        await msg.answer("🏓 Я на связи!")

@dp.message(F.text == "/pause")
async def cmd_pause(msg: Message):
    global is_paused
    if msg.chat.id == CHAT_ID:
        is_paused = True
        await msg.answer("⏸ Остановлено")

@dp.message(F.text == "/resume")
async def cmd_resume(msg: Message):
    global is_paused
    if msg.chat.id == CHAT_ID:
        is_paused = False
        await msg.answer("▶️ Возобновлено")

async def main():
    scheduler.add_job(check_arbitrage, 'interval', seconds=30)
    scheduler.start()
    await bot.send_message(CHAT_ID, "✅ Railway бот полностью работает.")
    await dp.start_polling(bot)

if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    def run_main():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    threading.Thread(target=run_main).start()
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
