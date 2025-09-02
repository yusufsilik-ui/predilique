from flask import Flask, render_template, request, redirect, url_for, flash
from binance.client import Client
from binance.enums import *
import os

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")  # For flash messages

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

client = Client(API_KEY, API_SECRET)

def set_leverage(symbol, leverage):
    client.futures_change_leverage(symbol=symbol, leverage=leverage)

def get_usdt_balance():
    balance = client.futures_account_balance()
    for asset in balance:
        if asset['asset'] == 'USDT':
            return float(asset['balance'])
    return 0.0

@app.route("/")
def index():
    btc_price = client.get_symbol_ticker(symbol="BTCUSDC")["price"]
    return render_template("index.html", title="Predilique", btc_price=btc_price)

@app.route("/trade", methods=["GET", "POST"])
def trade():
    symbol = "BTCUSDC"
    if request.method == "POST":
        side = request.form.get("side")  # BUY or SELL
        amount_usdt = request.form.get("amount_usdt")
        leverage = int(request.form.get("leverage", 1))
        all_in = request.form.get("all_in") == "on"

        try:
            set_leverage(symbol, leverage)

            if all_in:
                amount_usdt = get_usdt_balance()
            else:
                amount_usdt = float(amount_usdt)

            price = float(client.get_symbol_ticker(symbol=symbol)["price"])

            quantity = round(amount_usdt / price, 6)  # Adjust precision if needed

            order = client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY if side == "BUY" else SIDE_SELL,
                type=ORDER_TYPE_LIMIT,
                timeInForce=TIME_IN_FORCE_GTX,  # post-only
                price=str(price),
                quantity=quantity,
                reduceOnly=False,
                newOrderRespType='RESULT'
            )
            flash(f"Post-only limit order placed: {order['side']} {order['origQty']} {symbol} at {order['price']}", "success")
        except Exception as e:
            flash(f"Error placing order: {str(e)}", "danger")

        return redirect(url_for("trade"))

    usdt_balance = get_usdt_balance()
    return render_template("trade.html", usdt_balance=usdt_balance)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
