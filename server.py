from flask import Flask, render_template
from binance.client import Client
import os

app = Flask(__name__)

# Load Binance API keys from environment variables
API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

# Initialize Binance client
client = Client(API_KEY, API_SECRET)

@app.route("/")
def index():
    # Get current BTCUSDT price
    btc_price = client.get_symbol_ticker(symbol="BTCUSDT")["price"]
    return render_template("index.html", title="Predilique", btc_price=btc_price)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
