import logging
import asyncio
import aiohttp
import os
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()
API_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = int(os.getenv('TELEGRAM_CHAT_ID', '0'))
PRICE_DIFF_THRESHOLD = float(os.getenv('PRICE_DIFF_THRESHOLD', 0.001))

PAIRS = [
    'TRXUSDT', 'TRXUSDC', 'TRXWETH', 'TRXBTT', 'TRXJST',
    'TRXSUN', 'TRXUSDD', 'TRXFLUX', 'BTCTUSDT', 'TRXBTCT',
    'BTCUSDT', 'ETHUSDT', 'ETHTRX', 'BTCTRX', 'WETHUSDT',
    'USDCUSDT', 'USDCWETH', 'USDTBTT', 'USDTJST', 'USDTSUN'
]

EXCHANGES = {
    'Binance': lambda pair: f'https://api.binance.com/api/v3/ticker/price?symbol={pair}',
    'KuCoin': lambda pair: f'https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={pair[:3]}-{pair[3:]}',
    'MEXC': lambda pair: f'https://www.mexc.com/open/api/v2/market/ticker?symbol={pair[:3]}_{pair[3:]}',
    'OKX': lambda pair: f'https://www.okx.com/api/v5/market/ticker?instId={pair[:3]}-{pair[3:]}',
    'Bybit': lambda pair: f'https://api.bybit.com/v2/public/tickers?symbol={pair}'
}

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s:%(message)s')

async def fetch_price(exchange, pair):
    url = EXCHANGES[exchange](pair)
    headers = {'User-Agent': 'Mozilla/5.0'}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 403:
                    return None
                data = await resp.json()
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
        except Exception:
            return None

async def check_arbitrage():
    try:
        for pair in PAIRS:
            debug_message = f"🔍 Отладка {pair[:3]}/{pair[3:]}:\n"
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

            if len(prices) >= 2:
                exchanges = list(prices.keys())
                p1, p2 = prices[exchanges[0]], prices[exchanges[1]]
                diff = abs(p1 - p2) / min(p1, p2)
                debug_message += f"\nDiff: {diff*100:.2f}%\n"
                if diff >= PRICE_DIFF_THRESHOLD:
                    debug_message += "⚠️ Разница превышает порог!\n"

            await bot.send_message(CHAT_ID, debug_message)
    except Exception as e:
        await bot.send_message(CHAT_ID, f"❌ Ошибка в check_arbitrage: {e}")
        logging.error(f"Error checking arbitrage: {e}")

async def main():
    scheduler.add_job(check_arbitrage, 'interval', seconds=30)
    scheduler.start()
    await bot.send_message(CHAT_ID, "✅ Railway бот запущен. Проверяю 20 пар в корректном направлении.")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
