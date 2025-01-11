from telethon import TelegramClient, events
import asyncio
import requests
import time
import hmac
import hashlib
import math

# Replace 'session_name' with a unique name for your session file
client = TelegramClient('session_name', api_id, api_hash)

# MEXC API credentials
base_url = "https://api.mexc.com"

# Global variables
target_chat_id = None

def send_telegram_message(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.post(url, json=payload)
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}")


def create_signature(params):
    query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
    return hmac.new(mexc_api_secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()


def fetch_balance():
    endpoint = "/api/v3/account"
    url = base_url + endpoint
    timestamp = int(time.time() * 1000)
    params = {"timestamp": timestamp}
    params["signature"] = create_signature(params)

    headers = {"X-MEXC-APIKEY": mexc_api_key}
    response = requests.get(url, headers=headers, params=params)
    data = response.json()

    for asset in data.get("balances", []):
        if asset["asset"] == "USDT":
            return float(asset["free"])
    return 0


def round_down_to_two_decimals(amount):
    return math.floor(amount * 100) / 100


def is_symbol_supported(symbol):
    endpoint = "/api/v3/exchangeInfo"
    url = base_url + endpoint
    response = requests.get(url)
    data = response.json()

    symbols = [item['symbol'] for item in data.get('symbols', [])]
    return symbol in symbols


def fetch_minimum_quantity(symbol):
    endpoint = "/api/v3/exchangeInfo"
    url = base_url + endpoint
    response = requests.get(url)
    data = response.json()

    for item in data.get("symbols", []):
        if item["symbol"] == symbol:
            for filter_item in item["filters"]:
                if filter_item["filterType"] == "LOT_SIZE":
                    return float(filter_item["minQty"])
    return 1.0


def fetch_order_status(symbol, order_id):
    endpoint = "/api/v3/order"
    url = base_url + endpoint
    timestamp = int(time.time() * 1000)
    params = {
        "symbol": symbol,
        "orderId": order_id,
        "timestamp": timestamp,
    }
    params["signature"] = create_signature(params)

    headers = {"X-MEXC-APIKEY": mexc_api_key}
    response = requests.get(url, headers=headers, params=params)
    return response.json()


def place_order_with_usdt(symbol, side, quantity):
    quantity = round_down_to_two_decimals(quantity)

    endpoint = "/api/v3/order"
    url = base_url + endpoint
    timestamp = int(time.time() * 1000)
    params = {
        "symbol": symbol,
        "side": side.upper(),
        "type": "MARKET",
        "quantity": quantity,
        "timestamp": timestamp,
    }
    params["signature"] = create_signature(params)

    headers = {"X-MEXC-APIKEY": mexc_api_key}
    response = requests.post(url, headers=headers, params=params)
    return response.json()


def fetch_executed_price(order_id, symbol):
    order_details = fetch_order_status(symbol, order_id)
    executed_qty = float(order_details.get("executedQty", 0))
    cumulative_price = float(order_details.get("cummulativeQuoteQty", 0))
    if executed_qty > 0:
        executed_price = cumulative_price / executed_qty
        print(f"Executed price for {symbol}: {executed_price}")
        return executed_price
    return 0


def calculate_gross_profit_or_loss(buy_price, sell_price, quantity):
    """Calculate gross profit/loss without fees."""
    return (sell_price - buy_price) * quantity


def calculate_fees(buy_price, sell_price, quantity, trading_fee=0.0005):
    """Calculate total fees for both buy and sell transactions."""
    return (buy_price + sell_price) * quantity * trading_fee


def get_price(symbol):
    """
    Get the current price of the coin from MEXC.
    """
    endpoint = "/api/v3/ticker/price"
    url = base_url + endpoint
    response = requests.get(url, params={"symbol": symbol})
    data = response.json()

    if "price" in data:
        return float(data["price"])
    else:
        raise ValueError(f"Failed to fetch price for {symbol}: {data}")


async def monitor_profit_and_stop_loss(symbol, buy_order_id, filled_qty, min_quantity):
    buy_price = fetch_executed_price(buy_order_id, symbol)
    if not buy_price:
        print("Error: Could not fetch executed buy price. Exiting.")
        return

    trailing_stop_loss = buy_price * (1 - 0.01)  # 1% below the buy price
    max_price = buy_price
    print(f"Monitoring started for {symbol} with buy price {buy_price:.6f}")

    while True:
        current_price = get_price(symbol)
        gross_profit_or_loss = calculate_gross_profit_or_loss(buy_price, current_price, filled_qty)
        total_fees = calculate_fees(buy_price, current_price, filled_qty)

        # Update trailing stop-loss
        if current_price > max_price:
            max_price = current_price
            trailing_stop_loss = max_price * (1 - 0.005)  # Adjust stop-loss to 0.5% below max price

        print(f"Monitoring {symbol}: Current price = {current_price}, Max Price = {max_price:.6f}, "
              f"Trailing Stop-Loss = {trailing_stop_loss:.6f}, Gross P/L = {gross_profit_or_loss:.2f}, Fees = {total_fees:.6f}")

        # Stop-loss trigger
        if current_price <= trailing_stop_loss:
            print(f"Trailing stop-loss triggered for {symbol}. Selling...")
            await place_and_verify_sell(symbol, filled_qty, min_quantity, reason="Trailing stop-loss")
            return

        # Profit target trigger
        if gross_profit_or_loss >= 0.0001:  # Example: 0.01% gross profit for testing
            print(f"Profit target reached for {symbol}. Selling...")
            await place_and_verify_sell(symbol, filled_qty, min_quantity, reason="Profit target")
            return

        await asyncio.sleep(1)


async def place_and_verify_sell(symbol, filled_qty, min_quantity, reason):
    if filled_qty < min_quantity:
        print(f"Error: Filled quantity {filled_qty} is below minimum trading quantity {min_quantity}. Cannot place sell order.")
        return

    sell_response = place_order_with_usdt(symbol, "SELL", filled_qty)
    print(f"Sell order response ({reason}): {sell_response}")

    order_id = sell_response.get("orderId")
    if not order_id:
        print(f"Error: No order ID returned for sell order ({reason}).")
        return

    order_status = fetch_order_status(symbol, order_id)
    sold_qty = float(order_status.get("executedQty", 0))
    executed_sell_price = fetch_executed_price(order_id, symbol)
    gross_profit_or_loss = calculate_gross_profit_or_loss(fetch_executed_price(order_id, symbol), executed_sell_price, sold_qty)

    print(f"Sell order executed quantity ({reason}): {sold_qty}, Executed Sell Price = {executed_sell_price}, Final Gross P/L = {gross_profit_or_loss:.2f}")


async def main():
    print("Starting Telegram client...")
    await client.start()
    print("Client started successfully!")
    print("Listening for messages...")

    @client.on(events.NewMessage)
    async def handler(event):
        global target_chat_id

        if event.chat_id == 777000 or event.chat_id == 7778646211 : 
            return

        else: 
            send_telegram_message(f"MESSAGE RECEIVED ON TELEGRAM: CHAT ID: {event.chat_id} || MESSAGE: {event.text}")
            print(f"MESSAGE RECEIVED ON TELEGRAM: CHAT ID: {event.chat_id}")
            if "Next message is the coin name. Buy as fast as possible." in event.text:
                target_chat_id = event.chat_id
                print(f"Detected trigger message in chat {target_chat_id}. Waiting for the next message...")

            elif target_chat_id and event.chat_id == target_chat_id:
                coin_name = event.text.strip()
                symbol = f"{coin_name}USDT"

                if is_symbol_supported(symbol):
                    usdt_balance = fetch_balance()
                    usdt_balance = round_down_to_two_decimals(usdt_balance)

                    if usdt_balance < 10:
                        print(f"Error: Insufficient USDT balance ({usdt_balance}). Minimum required is 10 USDT.")
                        return

                    buy_response = place_order_with_usdt(symbol, "BUY", usdt_balance)
                    order_id = buy_response.get("orderId")

                    if not order_id:
                        print("Error: No order ID returned. Exiting.")
                        return

                    order_status = fetch_order_status(symbol, order_id)
                    filled_qty = float(order_status.get("executedQty", 0))

                    if filled_qty <= 0:
                        print("Error: Buy order was not filled. Exiting.")
                        return

                    min_quantity = fetch_minimum_quantity(symbol)
                    await monitor_profit_and_stop_loss(symbol, order_id, filled_qty, min_quantity)
                    print("Trade completed. Stopping bot...")
                    await client.disconnect()  # Disconnect after sell
                else:
                    print(f"Symbol {symbol} is not supported for trading.")

                client.remove_event_handler(handler, events.NewMessage)
                target_chat_id = None

        

    await client.run_until_disconnected()  # Keep running until disconnected


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
