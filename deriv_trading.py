import websocket
import json
import time
from collections import deque
import statistics

# ===== USER SETTINGS =====
API_TOKEN = "VWiEsRmwIKXUix9"  # Replace with your actual Deriv API token
SYMBOL = "R_75"                # Market symbol
TRADE_AMOUNT = 1               # Amount per trade in USD
TRADE_DURATION = 1             # Duration per trade in minutes
SMA_SHORT_PERIOD = 5           # Short SMA period
SMA_LONG_PERIOD = 20           # Long SMA period

# ===== WEBSOCKET SETTINGS =====
DERIV_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

# Store recent ticks
ticks = deque(maxlen=SMA_LONG_PERIOD)

# Last trade signal to avoid repeat trades
last_signal = None

def send_request(ws, data):
    """Send JSON request to Deriv API."""
    ws.send(json.dumps(data))

def place_trade(ws, trade_type):
    """Place a CALL or PUT trade."""
    contract_type = "CALL" if trade_type == "buy" else "PUT"
    print(f"[TRADE SIGNAL] {contract_type} — Sending order...")

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

def calculate_sma(values, period):
    """Calculate Simple Moving Average."""
    if len(values) < period:
        return None
    return statistics.mean(list(values)[-period:])

def on_open(ws):
    print("[CONNECTED] Authorizing...")
    send_request(ws, {"authorize": API_TOKEN})

def on_message(ws, message):
    global last_signal
    data = json.loads(message)

    # Successful authorization
    if "authorize" in data:
        if "error" in data:
            print(f"[ERROR] Authorization failed: {data['error']['message']}")
            ws.close()
        else:
            print("[AUTHORIZED] Streaming price data...")
            send_request(ws, {"ticks": SYMBOL})

    # Receiving price ticks
    elif "tick" in data:
        price = data["tick"]["quote"]
        ticks.append(price)
        print(f"[TICK] {SYMBOL}: {price}")

        sma_short = calculate_sma(ticks, SMA_SHORT_PERIOD)
        sma_long = calculate_sma(ticks, SMA_LONG_PERIOD)

        if sma_short and sma_long:
            print(f"[SMA] Short({SMA_SHORT_PERIOD}): {sma_short:.2f} | Long({SMA_LONG_PERIOD}): {sma_long:.2f}")

            # Detect crossover and place trade
            if sma_short > sma_long and last_signal != "buy":
                place_trade(ws, "buy")
                last_signal = "buy"
            elif sma_short < sma_long and last_signal != "sell":
                place_trade(ws, "sell")
                last_signal = "sell"

    # Proposal response (trade confirmation)
    elif "proposal" in data:
        if "error" in data:
            print(f"[ERROR] Proposal: {data['error']['message']}")
        else:
            print(f"[TRADE PLACED] Details: {data}")

def on_error(ws, error):
    print(f"[ERROR] {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"[DISCONNECTED] {close_status_code} - {close_msg}")
    print("Reconnecting in 5 seconds...")
    time.sleep(5)
    start_bot()

def start_bot():
    ws = websocket.WebSocketApp(
        DERIV_URL,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

if __name__ == "__main__":
    start_bot()
