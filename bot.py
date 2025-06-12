import logging
import asyncio
import aiohttp
import os
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import FastAPI
import uvicorn

# === LOAD ENV ===
load_dotenv()
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = int(os.getenv('TELEGRAM_CHAT_ID', '0'))
PRICE_DIFF_THRESHOLD = float(os.getenv('PRICE_DIFF_THRESHOLD', 0.005))

PAIRS = [
    'TRXUSDT', 'USDCTRX', 'WETHTRX', 'BTTTRX', 'JSTTRX', 'SUNTRX',
    'USDDTRX', 'FLUXTRX', 'USDTBTCT', 'BTCTTRX', 'BTCUSDT', 'ETHUSDT',
    'TRXETH', 'TRXBTC', 'USDTWETH', 'USDTUSDC', 'WETHUSDC',
    'BTTUSDT', 'JSTUSDT', 'SUNUSDT'
]

# === EXCHANGE ENDPOINT TEMPLATES ===
EXCHANGES = {
    'Binance': lambda pair: f'https://api.binance.com/api/v3/ticker/price?symbol={pair}',
    'KuCoin': lambda pair: f'https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={pair[:3]}-{pair[3:]}',
    'MEXC': lambda pair: f'https://www.mexc.com/open/api/v2/market/ticker?symbol={pair[:3]}_{pair[3:]}',
    'OKX': lambda pair: f'https://www.okx.com/api/v5/market/ticker?instId={pair[:3]}-{pair[3:]}',
    'Bybit': lambda pair: f'https://api.bybit.com/v2/public/tickers?symbol={pair}'
}

# === INIT ===
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()
logging.basicConfig(filename='arbitrage_bot.log', level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

app = FastAPI()

@app.get("/status")
def status():
    return {"running": True, "pairs": len(PAIRS), "exchanges": list(EXCHANGES.keys())}


async def fetch_price(exchange, pair):
    url = EXCHANGES[exchange](pair)
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.json()
            try:
                if exchange == 'Binance':
                    return float(data['price'])
                elif exchange == 'KuCoin':
                    return float(data['data']['price'])
                elif exchange == 'MEXC':
                    return float(data['data'][0]['last'])
                elif exchange == 'OKX':
                    return float(data['data'][0]['last'])
                elif exchange == 'Bybit':
                    return float(data['result'][0]['last_price'])
            except:
                return None


async def check_arbitrage():
    try:
        for pair in PAIRS:
            prices = {}
            for exchange in EXCHANGES:
                try:
                    price = await fetch_price(exchange, pair)
                    if price:
                        prices[exchange] = price
                except Exception as e:
                    logging.error(f"{exchange} fetch error for {pair}: {e}")

            exchanges = list(prices.keys())
            for i in range(len(exchanges)):
                for j in range(i + 1, len(exchanges)):
                    ex1, ex2 = exchanges[i], exchanges[j]
                    p1, p2 = prices[ex1], prices[ex2]
                    diff = abs(p1 - p2) / min(p1, p2)
                    if diff >= PRICE_DIFF_THRESHOLD:
                        message = (
                            f"⚠️ Arbitrage Alert!\n"
                            f"Pair: {pair[:3]}/{pair[3:]}\n"
                            f"{ex1}: {p1:.5f}\n"
                            f"{ex2}: {p2:.5f}\n"
                            f"Diff: {diff*100:.2f}%"
                        )
                        await bot.send_message(CHAT_ID, message)
                        logging.info(message)

        # Тестовое сообщение (при каждом запуске или проверке)
        await bot.send_message(CHAT_ID, "✅ Бот работает. Тестовое уведомление отправлено.")

    except Exception as e:
        logging.error(f"Error checking arbitrage: {e}")


async def main():
    scheduler.add_job(check_arbitrage, 'interval', seconds=30)
    scheduler.start()
    await dp.start_polling(bot)


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(main())
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))