import ccxt
import pandas as pd
import ta
import time
import logging
import os
import requests
import matplotlib.pyplot as plt
from dotenv import load_dotenv
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# === CONFIG ===
LIVE = False  # Switch to True for real trading
TRADE_SYMBOL = 'BTC/USDT'  # Make sure this is correct for the coin you want to use
TIMEFRAME = '5m'  # Timeframe for the data (e.g., 5 minutes)
RISK_PER_TRADE = 0.01  # 1% of balance
TAKE_PROFIT = 0.02  # 2% take profit
STOP_LOSS = 0.01  # 1% stop loss
TRADING_FEE = 0.001   # Binance ~0.1%
INITIAL_BALANCE = 1000
ENABLE_ALERTS = True
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ALERT_WEBHOOK = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
ENABLE_BACKTEST = True # Make sure this is set to True for backtesting
EXPORT_CSV = True
PLOT_CHART = True  # Ensure this is set to True to plot the chart after backtest

# === LOGGING ===
os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename="logs/trading_log.txt", level=logging.INFO, format='%(asctime)s %(message)s')

# === INIT BINANCE ===
api_key = os.getenv("BINANCE_API_KEY")
api_secret = os.getenv("BINANCE_SECRET_KEY")

binance = ccxt.binance({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'},
})

binance.set_sandbox_mode(True) # False for trading live

# === FUNCTIONS ===
def fetch_data(symbol, timeframe):
    ohlcv = binance.fetch_ohlcv(symbol, timeframe, limit=2000)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def apply_indicators(df):
    # Apply the indicators (EMA, RSI, MACD)
    ema = ta.trend.EMAIndicator(df['close'], window=20)
    df['ema'] = ema.ema_indicator()
    df['rsi'] = ta.momentum.rsi(df['close'], window=14)
    
    macd = ta.trend.MACD(df['close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['volume_ma'] = df['volume'].rolling(20).mean()
    df['ema50'] = ta.trend.ema_indicator(df['close'], window=50)

    df.dropna(inplace=True)
    return df

def get_balance():
    balance = binance.fetch_balance()
    return balance['USDT']['free']

def place_order(order_type, amount):
    if LIVE:
        if order_type == 'buy':
            return binance.create_market_buy_order(TRADE_SYMBOL, amount)
        else:
            return binance.create_market_sell_order(TRADE_SYMBOL, amount)
    else:
        print(f"[SIMULATION] {order_type.upper()} {amount} {TRADE_SYMBOL}")
        return { 'status': 'simulated', 'side': order_type, 'amount': amount }

def trade_signal(df):
    latest = df.iloc[-1]
    trend_up = latest['ema'] > latest['ema50']
    macd_crossover = latest['macd'] > latest['macd_signal'] and df.iloc[-2]['macd'] < df.iloc[-2]['macd_signal']
    
    volume_ok = latest['volume'] > latest['volume_ma']
    if trend_up and macd_crossover and latest['rsi'] < 60 and volume_ok:
        return 'buy'
    elif not trend_up:
        return 'sell'
    return 'hold'

def send_alert(message):
    if ENABLE_ALERTS:
        #to print the alert you receive in telegram in terminal as well
        #print(f"[ALERT] {message}")
        try:
            requests.post(ALERT_WEBHOOK, data={
                'chat_id': CHAT_ID,
                'text': message
            })
        except Exception as e:
            logging.error(f"Alert failed: {e}")

def backtest(df):
    trades = []
    holding = False
    entry_price = 0
    for i in range(2, len(df)):
        window = df.iloc[:i+1]
        signal = trade_signal(window)
        price = window.iloc[-1]['close']

        if signal == 'buy' and not holding:
            entry_price = price
            holding = True
            trades.append({'timestamp': window.iloc[-1]['timestamp'], 'type': 'buy', 'price': price})
        elif holding:

            tp_price = entry_price * (1 + TAKE_PROFIT)
            sl_price = entry_price * (1 - STOP_LOSS)

            if price >= tp_price or price <= sl_price or signal == 'sell':
               holding = False
               trades.append({
                 'timestamp': window.iloc[-1]['timestamp'],
                 'type': 'sell',
                 'price': price
                })
               
    balance = INITIAL_BALANCE           
    profit = 0
    wins = 0
    losses = 0
    trade_results = []

    for i in range(1, len(trades), 2):
        buy_price = trades[i-1]['price']
        sell_price = trades[i]['price']
        position_size = (balance * RISK_PER_TRADE) / buy_price
        pnl = (sell_price - buy_price) * position_size
        fee = (buy_price * position_size + sell_price * position_size) * TRADING_FEE
        pnl -= fee
        balance += pnl
        profit += pnl
        result = 'win' if pnl > 0 else 'loss'
        if pnl > 0:
            wins += 1
        else:
            losses += 1
        trade_results.append({
              'buy_time': trades[i-1]['timestamp'],
              'buy_price': buy_price,
              'sell_time': trades[i]['timestamp'],
              'sell_price': sell_price,
              'pnl': pnl,
              'result': result
        })
    print("Backtest Results:")
    print(f"Total Trades: {len(trade_results)}")
    print(f"Winning Trades: {wins}")
    print(f"Losing Trades: {losses}")
    print(f"Total Profit: {profit:.2f} USDT")
    print(f"Final Balance: {balance:.2f} USDT")

    if EXPORT_CSV:
        df.to_csv("logs/backtest_data.csv", index=False)
        pd.DataFrame(trade_results).to_csv("logs/trade_results.csv", index=False)
        print("CSV files saved to logs/")

    send_alert(f"Backtest Complete:\nProfit: {profit:.2f} USDT\nWins: {wins}\nLosses: {losses}")
    
    if PLOT_CHART:
        # Plot the graph here
        plt.figure(figsize=(12,6))

        plt.plot(df['timestamp'], df['close'], label="Price")

        buy_plotted = False
        sell_plotted = False

        for t in trade_results:

            if not buy_plotted:
                plt.scatter(t['buy_time'], t['buy_price'], color='green', marker='^', label='Buy')
                buy_plotted = True
            else:
                plt.scatter(t['buy_time'], t['buy_price'], color='green', marker='^')

            if not sell_plotted:
                plt.scatter(t['sell_time'], t['sell_price'], color='red', marker='v', label='Sell')
                sell_plotted = True
            else:
                plt.scatter(t['sell_time'], t['sell_price'], color='red', marker='v')

        plt.legend()
        plt.title("Backtest Trades")
        plt.xlabel("Time")
        plt.ylabel("Price")
        plt.grid()
        plt.tight_layout()
        plt.savefig("logs/backtest_chart.png")
        plt.show()
# === TEST TELEGRAM ALERT ===
def test_telegram_alert():
    message = "🚀 Hello Kartik! This is a test alert from your trading bot."
    try:
        response = requests.post(ALERT_WEBHOOK, data={
            'chat_id': CHAT_ID,
            'text': message
        })
        print("Telegram response:", response.text)
    except Exception as e:
        print("Telegram test failed:", e)

# Run test - Remove the comment line below for receiving telegram alerts
#test_telegram_alert()

# === MAIN ===
if ENABLE_BACKTEST:
    df = fetch_data(TRADE_SYMBOL, TIMEFRAME)
    df = apply_indicators(df)
    backtest(df)
else:
    print("Starting trading bot...")
    holding = False
    entry_price = 0
    trade_amount = 0

    while True:
        try:
            df = fetch_data(TRADE_SYMBOL, TIMEFRAME)
            df = apply_indicators(df)
            signal = trade_signal(df)
            price = df.iloc[-1]['close']

            print(f"Coin: {TRADE_SYMBOL}, Price: {price:.2f}, Signal: {signal.upper()}")
            logging.info(f"Coin: {TRADE_SYMBOL}, Price: {price:.2f}, Signal: {signal.upper()}")

            if signal == 'buy' and not holding:
                balance = get_balance()
                trade_amount = (balance * RISK_PER_TRADE) / price
                order = place_order('buy', round(trade_amount, 6))
                entry_price = price
                holding = True
                logging.info(f"BUY ORDER: {order}")
                send_alert(f"Bought {TRADE_SYMBOL} at {price:.2f}")

            elif signal == 'sell' and holding:
                order = place_order('sell', round(trade_amount, 6))
                holding = False
                logging.info(f"SELL ORDER: {order}")
                send_alert(f"Sold {TRADE_SYMBOL} at {price:.2f}")

            elif holding:
                if price >= entry_price * (1 + TAKE_PROFIT):
                    order = place_order('sell', round(trade_amount, 6))
                    holding = False
                    logging.info("TAKE PROFIT triggered")
                    send_alert("Take profit hit")

                elif price <= entry_price * (1 - STOP_LOSS):
                    order = place_order('sell', round(trade_amount, 6))
                    holding = False
                    logging.info("STOP LOSS triggered")
                    send_alert("Stop loss hit")

            time.sleep(60)


        except Exception as e:
            print(f"Error: {e}")
            logging.error(f"Error: {e}")
            time.sleep(10)
        #  cd C:\Users\OO7\.vscode\bot
        #  .\venv\Scripts\Activate