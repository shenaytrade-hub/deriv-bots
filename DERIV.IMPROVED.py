import websocket
import json
import time
import csv
from collections import deque
import statistics
from datetime import datetime
import threading

# ===== USER SETTINGS =====
API_TOKEN = "VWiEsRmwIKXUix9"  # Replace with your actual Deriv API token
SYMBOL = "R_75"                # Market symbol
TRADE_AMOUNT = 1               # Amount per trade in USD
TRADE_DURATION = 1             # Duration per trade in minutes
SMA_SHORT_PERIOD = 5           # Short SMA period
SMA_LONG_PERIOD = 20           # Long SMA period

# ===== SAFETY SETTINGS =====
STOP_LOSS = -10               # Stop if loss reaches -$10
TAKE_PROFIT = 20              # Stop if profit reaches $20
MAX_TRADES = 10               # Stop after 10 trades
TRADE_COOLDOWN = 60           # Wait 60 seconds between trades

# ===== WEBSOCKET SETTINGS =====
DERIV_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

# ===== GLOBAL STATE =====
ticks = deque(maxlen=SMA_LONG_PERIOD)
last_signal = None
trade_count = 0
profit_loss = 0.0
last_trade_time = 0
balance = 0.0
bot_running = True  # Flag to stop the bot safely

LOG_FILE = "trade_history.csv"

def log_trade(trade_type, amount, pnl, new_balance):
    """Append trade details to CSV file."""
    with open(LOG_FILE, mode="a", newline="") as file:
        writer = csv.writer(file)
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            trade_type,
            amount,
            pnl,
            new_balance
        ])

def send_request(ws, data):
    ws.send(json.dumps(data))

def place_trade(ws, trade_type):
    global trade_count, last_trade_time, profit_loss, bot_running

    # Safety checks
    if trade_count >= MAX_TRADES:
        print("\n[STOP] 🚫 Maximum trades reached. Bot stopped.\n")
        bot_running = False
        ws.close()
        return
    if profit_loss <= STOP_LOSS:
        print(f"\n[STOP] ❌ Stop-loss hit at {profit_loss:.2f} USD. Bot stopped.\n")
        bot_running = False
        ws.close()
        return
    if profit_loss >= TAKE_PROFIT:
        print(f"\n[STOP] ✅ Take-profit hit at {profit_loss:.2f} USD. Bot stopped.\n")
        bot_running = False
        ws.close()
        return
    if time.time() - last_trade_time < TRADE_COOLDOWN:
        cooldown_remaining = int(TRADE_COOLDOWN - (time.time() - last_trade_time))
        print(f"[WAIT] ⏳ Cooldown active ({cooldown_remaining}s left). Trade skipped.")
        return

    # Change CALL/PUT to RISE/FALL
    contract_type = "RISE" if trade_type == "buy" else "FALL"
    print(f"\n[TRADE SIGNAL] 📈 {contract_type} — Sending order...\n")

    proposal = {
        "proposal": 1,
        "amount": TRADE_AMOUNT,
        "basis": "stake",
        "contract_type": contract_type,
        "currency": "USD",
        "duration": TRADE_DURATION,
        "duration_unit": "m",
        "symbol": SYMBOL
    }
    send_request(ws, proposal)
    last_trade_time = time.time()
    trade_count += 1

def calculate_sma(values, period):
    if len(values) < period:
        return None
    return statistics.mean(list(values)[-period:])

def print_live_profit():
    """Prints live profit/loss every 10 seconds while the bot runs."""
    while bot_running:
        print(f"[LIVE PROFIT] 💰 Session P/L: {profit_loss:.2f} USD | Trades executed: {trade_count}")
        time.sleep(10)

def on_open(ws):
    print("[CONNECTED] 🔐 Authorizing...")
    send_request(ws, {"authorize": API_TOKEN})

def on_message(ws, message):
    global last_signal, profit_loss, balance
    data = json.loads(message)

    # Authorization response
    if "authorize" in data:
        if "error" in data:
            print(f"[ERROR] Authorization failed: {data['error']['message']}")
            ws.close()
        else:
            balance = float(data["authorize"].get("balance", 0.0))
            print(f"[AUTHORIZED] ✅ Balance: {balance:.2f} USD")
            print("[AUTHORIZED] Streaming price data...")
            send_request(ws, {"ticks": SYMBOL})

    # Tick data received
    elif "tick" in data:
        price = float(data["tick"]["quote"])
        ticks.append(price)
        print(f"[TICK] {SYMBOL}: {price:.2f}")

        sma_short = calculate_sma(ticks, SMA_SHORT_PERIOD)
        sma_long = calculate_sma(ticks, SMA_LONG_PERIOD)

        if sma_short and sma_long:
            print(f"[SMA] Short({SMA_SHORT_PERIOD}): {sma_short:.2f} | Long({SMA_LONG_PERIOD}): {sma_long:.2f}")
            if sma_short > sma_long and last_signal != "buy":
                place_trade(ws, "buy")
                last_signal = "buy"
            elif sma_short < sma_long and last_signal != "sell":
                place_trade(ws, "sell")
                last_signal = "sell"

    # Trade proposal confirmed
    elif "proposal" in data and "error" not in data:
        print("[TRADE PLACED] 🟢 Waiting for contract result...")

    # Contract result (profit update)
    elif "profit" in data:
        pnl = float(data.get("profit", 0))
        profit_loss += pnl
        balance += pnl
        print(f"[RESULT] 📊 Trade P/L: {pnl:.2f} | Session P/L: {profit_loss:.2f} | New Balance: {balance:.2f}")
        log_trade(last_signal, TRADE_AMOUNT, pnl, balance)

def on_error(ws, error):
    print(f"[ERROR] ⚠️ {error}")

def on_close(ws, close_status_code, close_msg):
    global bot_running
    print(f"[DISCONNECTED] ❌ {close_status_code} - {close_msg}")
    bot_running = False
    print("Reconnecting in 5 seconds...")
    time.sleep(5)
    start_bot()

def start_bot():
    global bot_running, profit_loss, trade_count, last_signal, last_trade_time

    # Reset session state
    bot_running = True
    profit_loss = 0.0
    trade_count = 0
    last_signal = None
    last_trade_time = 0

    ws = websocket.WebSocketApp(
        DERIV_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )

    # Start live profit tracker thread
    profit_thread = threading.Thread(target=print_live_profit, daemon=True)
    profit_thread.start()

    ws.run_forever()

if __name__ == "__main__":
    # Create CSV file with headers if it doesn't exist
    try:
        with open(LOG_FILE, mode="x", newline="") as file:
            writer = csv.writer(file)
            writer.writerow(["Date/Time", "Trade Type", "Amount", "P/L", "Balance"])
    except FileExistsError:
        pass

    print("Bot starting... Current balance will be displayed upon authorization.")
    start_bot()
