import websocket
import json
import time

# ===== USER SETTINGS =====
API_TOKEN = "VWiEsRmwIKXUix9"  # Replace with your actual Deriv API token
SYMBOL = "R_75"  # Volatility 75 Index

# ===== WEBSOCKET SETTINGS =====
DERIV_URL = "wss://ws.derivws.com/websockets/v3?app_id=1089"

def send_request(ws, data):
    """Send JSON request to Deriv API."""
    ws.send(json.dumps(data))

def on_open(ws):
    print("[CONNECTED] Authorizing...")
    send_request(ws, {"authorize": API_TOKEN})

def on_message(ws, message):
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
        print(f"[TICK] {SYMBOL}: {price}")

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
