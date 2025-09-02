from flask import Flask, render_template, request, redirect, url_for, flash
from binance.client import Client
from binance.enums import *
import os
import math
import threading
import time

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")

API_KEY = os.getenv("BINANCE_API_KEY")
API_SECRET = os.getenv("BINANCE_API_SECRET")

client = Client(API_KEY, API_SECRET)

symbol = "BTCUSDC"
order_update_interval = 3  # seconds between order book checks

active_order = {
    "orderId": None,
    "side": None,
    "quantity": None,
    "thread": None,
    "stop_thread": False,
    "price_str": None,
    "reduce_only": False
}

def round_down(value, step):
    return math.floor(value / step) * step

def count_decimals(number):
    s = f"{number:.8f}".rstrip('0')
    if '.' in s:
        return len(s.split('.')[1])
    else:
        return 0

def cancel_active_order():
    if active_order["orderId"]:
        try:
            client.futures_cancel_order(symbol=symbol, orderId=active_order["orderId"])
            print(f"Cancelled order {active_order['orderId']}")
        except Exception as e:
            print(f"Error cancelling order: {e}")
        active_order["orderId"] = None

def place_post_only_order(side, quantity, price_str, reduce_only):
    order = client.futures_create_order(
        symbol=symbol,
        side=SIDE_BUY if side == "BUY" else SIDE_SELL,
        type=ORDER_TYPE_LIMIT,
        timeInForce=TIME_IN_FORCE_GTX,  # post-only
        price=price_str,
        quantity=quantity,
        reduceOnly=reduce_only,
        newOrderRespType='RESULT'
    )
    print(f"Placed {side} order (reduceOnly={reduce_only}): ID {order['orderId']} qty {order['origQty']} price {order['price']}")
    return order

def order_updater(side, quantity, step_size, tick_size, reduce_only):
    global active_order
    while not active_order["stop_thread"]:
        try:
            depth = client.futures_order_book(symbol=symbol, limit=5)
            bids = depth['bids']
            asks = depth['asks']

            best_bid_price = float(bids[0][0])
            best_ask_price = float(asks[0][0])

            if side == "BUY":
                target_price = best_bid_price + tick_size
            else:
                target_price = best_ask_price - tick_size

            target_price = round_down(target_price, tick_size)
            price_decimals = count_decimals(tick_size)
            price_str = f"{target_price:.{price_decimals}f}"

            if (active_order["orderId"] is None) or (active_order.get("price_str") != price_str):
                if active_order["orderId"]:
                    cancel_active_order()

                order = place_post_only_order(side, quantity, price_str, reduce_only)
                active_order["orderId"] = order['orderId']
                active_order["price_str"] = price_str

            time.sleep(order_update_interval)
        except Exception as e:
            print(f"Error in order updater thread: {e}")
            time.sleep(order_update_interval)

@app.route("/trade", methods=["GET", "POST"])
def trade():
    global active_order

    if request.method == "POST":
        side = request.form.get("side")  # BUY or SELL
        amount_usdt = request.form.get("amount_usdt")
        leverage = int(request.form.get("leverage", 1))
        all_in = request.form.get("all_in") == "on"
        reduce_only = request.form.get("reduce_only") == "on"

        try:
            # Set leverage
            client.futures_change_leverage(symbol=symbol, leverage=leverage)

            if all_in:
                amount_usdt = float(get_usdt_balance())
            else:
                amount_usdt = float(amount_usdt)

            price = float(client.get_symbol_ticker(symbol=symbol)["price"])

            exchange_info = client.futures_exchange_info()
            symbol_info = next(filter(lambda s: s['symbol'] == symbol, exchange_info['symbols']), None)
            if not symbol_info:
                flash("Symbol info not found", "danger")
                return redirect(url_for("trade"))

            lot_size_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE')
            step_size = float(lot_size_filter['stepSize'])

            price_filter = next(f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER')
            tick_size = float(price_filter['tickSize'])

            quantity = amount_usdt / price
            quantity = round_down(quantity, step_size)

            quantity_decimals = count_decimals(step_size)
            quantity_str = f"{quantity:.{quantity_decimals}f}"

            # Stop previous thread if running
            if active_order["thread"] and active_order["thread"].is_alive():
                active_order["stop_thread"] = True
                active_order["thread"].join()

            active_order = {
                "orderId": None,
                "side": side,
                "quantity": quantity_str,
                "thread": None,
                "stop_thread": False,
                "price_str": None,
                "reduce_only": reduce_only
            }

            # Start background thread to manage order updates
            thread = threading.Thread(target=order_updater, args=(side, quantity_str, step_size, tick_size, reduce_only))
            thread.daemon = True
            thread.start()
            active_order["thread"] = thread

            flash(f"Started {'reduce-only ' if reduce_only else ''}post-only {side} order updater with quantity {quantity_str}", "success")

        except Exception as e:
            import traceback
            print(traceback.format_exc())
            flash(f"Error placing order: {str(e)}", "danger")

        return redirect(url_for("trade"))

    usdt_balance = get_usdt_balance()
    return render_template("trade.html", usdt_balance=usdt_balance)
