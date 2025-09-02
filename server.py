from flask import Flask, render_template, request, redirect, url_for, flash
from binance.client import Client
from binance.enums import *
import os
import math

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

def round_down(value, step):
    return math.floor(value / step) * step

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

            # Get current price
            price = float(client.get_symbol_ticker(symbol=symbol)["price"])

            # Get symbol info for precision
            exchange_info = client.futures_exchange_info()
            symbol_info = next(filter(lambda s: s['symbol'] == symbol, exchange_info['symbols']), None)
            if not symbol_info:
                flash("Symbol info not found", "danger")
                return redirect(url_for("trade"))

            # Extract stepSize and tickSize
            lot_size_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')
            step_size = float(lot_size_filter['stepSize'])

            price_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER')
            tick_size = float(price_filter['tickSize'])

            # Calculate quantity and round down
            quantity = amount_usdt / price
            quantity = round_down(quantity, step_size)

            # Round price down
            price = round_down(price, tick_size)

            # Format strings with correct decimals
            def count_decimals(number):
                s = f"{number:.8f}".rstrip('0')
                if '.' in s:
                    return len(s.split('.')[1])
                else:
                    return 0

            quantity_decimals = count_decimals(step_size)
            price_decimals = count_decimals(tick_size)

            quantity_str = f"{quantity:.{quantity_decimals}f}"
            price_str = f"{price:.{price_decimals}f}"

            order = client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY if side == "BUY" else SIDE_SELL,
                type=ORDER_TYPE_LIMIT,
                timeInForce=TIME_IN_FORCE_GTX,  # post-only
                price=price_str,
                quantity=quantity_str,
                reduceOnly=False,
                newOrderRespType='RESULT'
            )
            flash(f"Post-only limit order placed: {order['side']} {order['origQty']} {symbol} at {order['price']}", "success")
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            flash(f"Error placing order: {str(e)}", "danger")

        return redirect(url_for("trade"))

    usdt_balance = get_usdt_balance()
    return render_template("trade.html", usdt_balance=usdt_balance)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
