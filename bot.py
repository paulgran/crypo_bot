import logging
import asyncio
import aiohttp
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn
from threading import Thread

load_dotenv()
API_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID", "0"))
PRICE_DIFF_THRESHOLD = float(os.getenv("PRICE_DIFF_THRESHOLD", 0.005))

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
is_paused = False

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
        except:
            return None

async def check_arbitrage():
    if is_paused:
        return
    for pair in PAIRS:
        prices = {}
        for exchange in EXCHANGES:
            price = await fetch_price(exchange, pair)
            if price:
                prices[exchange] = price
        if len(prices) >= 2:
            exs = list(prices.keys())
            p1, p2 = prices[exs[0]], prices[exs[1]]
            diff = abs(p1 - p2) / min(p1, p2)
            if diff >= PRICE_DIFF_THRESHOLD:
                msg = f"📈 <b>Выгодная пара {pair[:3]}/{pair[3:]}:</b>\n"
                for ex in prices:
                    msg += f"{ex}: {prices[ex]:.5f}\n"
                msg += f"\n<b>Diff:</b> {diff*100:.2f}% ⚠️"
                await bot.send_message(CHAT_ID, msg)

@dp.message(F.text == "/start")
async def cmd_start(msg: Message):
    if msg.chat.id == CHAT_ID:
        await msg.answer("🤖 Бот готов. Введите /help для команд.")

@dp.message(F.text == "/help")
async def cmd_help(msg: Message):
    if msg.chat.id == CHAT_ID:
        await msg.answer("""🛠 Команды:
/ping
/pause
/resume
/threshold 0.002
/help""")

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

@dp.message(F.text.startswith("/threshold"))
async def cmd_threshold(msg: Message):
    global PRICE_DIFF_THRESHOLD
    if msg.chat.id == CHAT_ID:
        try:
            val = float(msg.text.split()[1])
            PRICE_DIFF_THRESHOLD = val
            await msg.answer(f"🔧 Порог обновлён: {val}")
        except:
            await msg.answer("⚠️ Формат: /threshold 0.005")

async def main():
    scheduler.add_job(check_arbitrage, "interval", seconds=30)
    scheduler.start()
    await bot.send_message(CHAT_ID, "✅ Railway бот запущен.")
    await dp.start_polling(bot)

def run_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

if __name__ == "__main__":
    Thread(target=run_fastapi).start()
    asyncio.run(main())
