
import logging
import asyncio
import aiohttp
import os
from aiogram import Bot, Dispatcher, F
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
PRICE_DIFF_THRESHOLD = float(os.getenv("PRICE_DIFF_THRESHOLD", 0.001))

PAIRS = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "TRXUSDT",
    "LINKUSDT", "DOTUSDT", "MATICUSDT", "LTCUSDT", "AVAXUSDT", "ATOMUSDT", "OPUSDT", "ARBUSDT",
    "APTUSDT", "ETCUSDT", "UNIUSDT", "XMRUSDT", "FILUSDT", "EOSUSDT", "AAVEUSDT", "NEARUSDT",
    "PEPEUSDT", "SHIBUSDT", "GALAUSDT", "RUNEUSDT", "SANDUSDT", "MANAUSDT", "CRVUSDT", "ALGOUSDT",
    "ZILUSDT", "CROUSDT", "BCHUSDT", "DYDXUSDT", "GMXUSDT", "INJUSDT", "STXUSDT", "SNXUSDT"
]

EXCHANGES = {
    "Binance": lambda pair: f"https://api.binance.com/api/v3/ticker/price?symbol={pair}",
    "KuCoin": lambda pair: f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={pair[:3]}-{pair[3:]}",
    "MEXC": lambda pair: f"https://www.mexc.com/open/api/v2/market/ticker?symbol={pair[:3]}_{pair[3:]}",
    "OKX": lambda pair: f"https://www.okx.com/api/v5/market/ticker?instId={pair[:3]}-{pair[3:]}",
    "Bybit": lambda pair: f"https://api.bybit.com/v2/public/tickers?symbol={pair}",
    "Gate.io": lambda pair: f"https://api.gate.io/api2/1/ticker/{pair.lower()}",
    "Huobi": lambda pair: f"https://api.huobi.pro/market/detail/merged?symbol={pair.lower()}",
    "Bitfinex": lambda pair: f"https://api-pub.bitfinex.com/v2/ticker/t{pair}"
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
            async with session.get(url, headers=headers, timeout=8) as resp:
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
                elif exchange == "Gate.io":
                    return float(data["last"])
                elif exchange == "Huobi":
                    return float(data["tick"]["close"])
                elif exchange == "Bitfinex":
                    return float(data[6])
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
            for i in range(len(exs)):
                for j in range(i+1, len(exs)):
                    a, b = exs[i], exs[j]
                    p1, p2 = prices[a], prices[b]
                    diff = abs(p1 - p2) / min(p1, p2)
                    if diff >= PRICE_DIFF_THRESHOLD:
                        percent = diff * 100
                        msg = f"📊 <b>{pair[:3]}/{pair[3:]}</b>\n"
                        msg += f"{a}: {p1:.4f}\n"
                        msg += f"{b}: {p2:.4f}\n"
                        msg += f"\nDiff: {percent:.2f}% ⚠️"
                        await bot.send_message(CHAT_ID, msg)

@dp.message(F.text == "/start")
async def cmd_start(msg: Message):
    if msg.chat.id == CHAT_ID:
        await msg.answer("🤖 Бот запущен. Введите /help для команд.")

@dp.message(F.text == "/help")
async def cmd_help(msg: Message):
    await msg.answer("🧠 Команды:\n/ping\n/pause\n/resume\n/threshold 0.005")

@dp.message(F.text == "/ping")
async def cmd_ping(msg: Message):
    await msg.answer("🏓 Я на связи!")

@dp.message(F.text == "/pause")
async def cmd_pause(msg: Message):
    global is_paused
    is_paused = True
    await msg.answer("⏸ Остановлено")

@dp.message(F.text == "/resume")
async def cmd_resume(msg: Message):
    global is_paused
    is_paused = False
    await msg.answer("▶️ Возобновлено")

@dp.message(F.text.startswith("/threshold"))
async def cmd_threshold(msg: Message):
    global PRICE_DIFF_THRESHOLD
    try:
        val = float(msg.text.split()[1])
        PRICE_DIFF_THRESHOLD = val
        await msg.answer(f"✅ Новый порог: {val}")
    except:
        await msg.answer("⚠️ Формат: /threshold 0.005")

async def main():
    scheduler.add_job(check_arbitrage, "interval", seconds=30)
    scheduler.start()
    await bot.send_message(CHAT_ID, "✅ Бот полностью активен.")
    await dp.start_polling(bot)

def run_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))

if __name__ == "__main__":
    Thread(target=run_fastapi).start()
    asyncio.run(main())
