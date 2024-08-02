import requests
from bs4 import BeautifulSoup
import asyncio
from typing import Final
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, JobQueue
import json

# Define the allUSDpairs array globally in Yahoo Finance format
allUSDpairs = ["EUR/USD", "GBP/USD", "USD/JPY", "USD/CHF", "AUD/USD", "USD/CAD", "NZD/USD", "XAU/USD"]

tradeHistory = []
determinedDecision = []  # Declare determinedDecision globally

API_KEY = '5cm4WxOPEa7zhsOESBoF71zmG5MGeFbDarx5xcsq'
base_url = 'https://yfapi.net/v6/finance/quote'
headers = {'x-api-key': API_KEY}

TOKEN: Final = '6993882268:AAE50k5b32rYzVIqgWmpOCDZi9CnB3vebdk'
BOT_USERNAME: Final = '@shootercrow_bot'

# Dictionary to keep track of user states
user_signal_status = {}

def remove_K_and_convert_to_int(value):
    if value == "N/A":
        return None
    else:
        return int(value.replace('K', ''))

def get_exchange_rate(pair):
    url = f"{base_url}?symbols={pair}"
    response = requests.get(url, headers=headers)
    data = response.json()
    if "quoteResponse" in data and data["quoteResponse"]["result"]:
        return data["quoteResponse"]["result"][0]
    else:
        return None

def get_current_prices():
    prices = {}
    for pair in allUSDpairs:
        result = get_exchange_rate(pair)
        if result:
            pair_name = result['symbol']
            price = result['regularMarketPrice']
            prices[pair_name] = price
            print(f"{pair_name}: {price}")
        else:
            print(f"Error fetching data for {pair}")
    return prices

def analyze_nfp(actual, forecast, previous):
    actualInt = remove_K_and_convert_to_int(actual)
    forecastInt = remove_K_and_convert_to_int(forecast)
    previousInt = remove_K_and_convert_to_int(previous)

    if actualInt is None or forecastInt is None or previousInt is None:
        return "Insufficient data to make a decision."

    if actualInt > forecastInt and actualInt > previousInt:
        return "Buy USD"
    elif actualInt > forecastInt and actualInt < previousInt:
        return "Cautious Buy USD"
    elif actualInt > forecastInt and actualInt == previousInt:
        return "Buy USD"
    elif actualInt < forecastInt and actualInt > previousInt:
        return "Cautious Sell USD"
    elif actualInt < forecastInt and actualInt < previousInt:
        return "Sell USD"
    elif actualInt < forecastInt and actualInt == previousInt:
        return "Sell USD"
    elif actualInt == forecastInt and actualInt > previousInt:
        return "Buy USD"
    elif actualInt == forecastInt and actualInt < previousInt:
        return "Cautious Sell USD"
    elif actualInt == forecastInt and actualInt == previousInt:
        return "Hold USD"

def analyze_fed_interest_rate(actual, forecast, previous):
    actual_rate = float(actual.replace('%', ''))
    forecast_rate = float(forecast.replace('%', ''))
    previous_rate = float(previous.replace('%', ''))

    if actual_rate == forecast_rate and actual_rate == previous_rate:
        return "Hold USD"
    elif actual_rate > forecast_rate and actual_rate > previous_rate:
        return "Buy USD"
    elif actual_rate < forecast_rate and actual_rate < previous_rate:
        return "Sell USD"
    elif actual_rate > forecast_rate and actual_rate < previous_rate:
        return "Cautious Buy USD"
    elif actual_rate < forecast_rate and actual_rate > previous_rate:
        return "Cautious Sell USD"
    else:
        return "Mixed signals, hold position."

def analyze_gdp(actual, forecast, previous):
    actual_rate = float(actual.replace('%', ''))
    forecast_rate = float(forecast.replace('%', ''))
    previous_rate = float(previous.replace('%', ''))

    if actual_rate > forecast_rate and actual_rate > previous_rate:
        return "Buy USD"
    elif actual_rate > forecast_rate and actual_rate < previous_rate:
        return "Cautious Buy USD"
    elif actual_rate > forecast_rate and actual_rate == previous_rate:
        return "Buy USD"
    elif actual_rate < forecast_rate and actual_rate > previous_rate:
        return "Cautious Sell USD"
    elif actual_rate < forecast_rate and actual_rate < previous_rate:
        return "Sell USD"
    elif actual_rate < forecast_rate and actual_rate == previous_rate:
        return "Sell USD"
    elif actual_rate == forecast_rate and actual_rate > previous_rate:
        return "Buy USD"
    elif actual_rate == forecast_rate and actual_rate < previous_rate:
        return "Cautious Sell USD"
    elif actual_rate == forecast_rate and actual_rate == previous_rate:
        return "Hold USD"

def fetch_financial_data():
    url = "https://www.investing.com/economic-calendar/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    print("Fetching data from the website...")
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        print("Page loaded successfully.")
    except requests.RequestException as e:
        print(f"Error fetching data: {e}")
        return None

    soup = BeautifulSoup(response.content, 'html.parser')
    calendar_table = soup.find('table', {'id': 'economicCalendarData'})
    headers = [header.text.strip() for header in calendar_table.find_all('th')]

    global determinedDecision  # Use the global determinedDecision variable
    determinedDecision = []

    for row in calendar_table.find_all('tr'):
        cols = row.find_all('td')
        if len(cols) > 0:
            row_data = [col.text.strip() if col.text.strip() else "N/A" for col in cols]
            while len(row_data) < len(headers):
                row_data.append("N/A")

            if any(col and "Nonfarm Payrolls" in col for col in row_data) and not any(col and "Private Nonfarm Payrolls" in col for col in row_data):
                date, time, currency, event, actual, forecast, previous = row_data[:7]
                print(f"Currency: {currency}, Event: {event}, Actual: {actual}, Forecast: {forecast}, Previous: {previous}")
                decision = analyze_nfp(actual, forecast, previous)
                print(f"NFP Decision: {decision}")
                determinedDecision.append({"event": event, "decision": decision})
                tradeHistory.append({"event": event, "decision": decision, "time": time})

            if any(col and "Fed Interest Rate Decision" in col for col in row_data):
                date, time, currency, event, actual, forecast, previous = row_data[:7]
                print(f"Currency: {currency}, Event: {event}, Actual: {actual}, Forecast: {forecast}, Previous: {previous}")
                decision = analyze_fed_interest_rate(actual, forecast, previous)
                print(f"Fed Interest Rate Decision: {decision}")
                determinedDecision.append({"event": event, "decision": decision})
                tradeHistory.append({"event": event, "decision": decision, "time": time})

            if any(col and "GDP (QoQ) (Q1)" in col for col in row_data):
                date, time, currency, event, actual, forecast, previous = row_data[:7]
                print(f"Currency: {currency}, Event: {event}, Actual: {actual}, Forecast: {forecast}, Previous: {previous}")
                decision = analyze_gdp(actual, forecast, previous)
                print(f"GDP Decision: {decision}")
                determinedDecision.append({"event": event, "decision": decision})
                tradeHistory.append({"event": event, "decision": decision, "time": time})

    if not determinedDecision:
        print("No relevant events found.")
    else:
        print("All relevant events found and decisions made.")

def send_to_user():
    fetch_financial_data()
    if not determinedDecision:
        return "No relevant events found."
    decision_messages = [f"Event: {decision['event']}\nDecision: {decision['decision']}" for decision in determinedDecision]
    return "\n\n".join(decision_messages)

async def continuous_data_processing(context: ContextTypes.DEFAULT_TYPE):
    prices = get_current_prices()
    for pair, currentPrice in prices.items():
        trade_obj = {
            "pairname": pair,
            "currentPrice": currentPrice,
            "price24HoursLater": None,
            "profitLoss": None
        }
        tradeHistory.append(trade_obj)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"""👋 Hey *{update.message.from_user.first_name}*, Welcome to the *ShooterCrowFX Bot!* 🎉\n\n 🔔 ShooterCrowFX analysis fundamental events and gives you a clear direction of BUY or SELL, a couple times a month so watch out regularly 🚀.\n💡 Simply click the 'Receive Signals 🔴' button below to start getting signals, when available.\n📊 Stay ahead of the market trends and never miss a profitable opportunity.\n💬 Click 'Receive Signals 🔴' to get started!\n
PS. No Technical Analysis Involved\n💡Always ON Receive Signals on the First Friday of Every Month.""", parse_mode='Markdown')

    # Introduce a delay before sending the first message
    await asyncio.sleep(2)

    await update.message.reply_text("""ShooterCrowFX 🤖 Welcomes You Once More!""",
                                    parse_mode='Markdown',
                                    reply_markup=ReplyKeyboardMarkup(
                                        [[KeyboardButton("Not Receiving Signals. 🔴 (Click to Start)")]],
                                        resize_keyboard=True
                                    )
                                    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"""Hello {update.message.from_user.first_name}, how can I help you?""")

def handle_response(text: str) -> str:
    def trade_history_finder():
        if not tradeHistory:
            return "No trade history yet."
        else:
            return tradeHistory
    processed: str = text.lower()
    if '/about' in processed:
        return '🔔 ShooterCrowFX analysis fundamental events and gives you a clear direction of BUY or SELL, a couple times a month so watch out regularly 🚀.'
    if '/history' in processed:
        trade_history_str = json.dumps(tradeHistory, indent=2)
        return f"Trade History:\n{trade_history_finder()}"
    return 'I do not understand'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    message_type: str = update.message.chat.type
    text: str = update.message.text

    print(f'User({update.message.chat.id}) in {message_type}: "{text}"')

    if message_type == 'group':
        if BOT_USERNAME in text:
            new_text: str = text.replace(BOT_USERNAME, '').strip()
            response: str = handle_response(new_text)
        else:
            return
    else:
        response: str = handle_response(text)

    if text == "Not Receiving Signals. 🔴 (Click to Start)" or text == "Receiving Signals... 🟢 (Click to Stop)":
        if user_signal_status.get(user_id):
            user_signal_status[user_id] = False
            response = "You have stopped receiving signals."
            new_button_text = "Not Receiving Signals. 🔴 (Click to Start)"
        else:
            user_signal_status[user_id] = True
            response = """You have started receiving signals 🟢.
(Signals are updated every minute.)"""
            new_button_text = "Receiving Signals... 🟢 (Click to Stop)"
            asyncio.create_task(send_signal_reminder(update, context, user_id))

        await update.message.reply_text(
            response,
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton(new_button_text)]],
                resize_keyboard=True
            )
        )
        return

    print('Bot:', response)
    await update.message.reply_text(response)

async def send_signal_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int):
    while user_signal_status.get(user_id):
        await asyncio.sleep(60)
        if user_signal_status.get(user_id):
            await context.bot.send_message(chat_id=user_id, text=send_to_user())

async def error(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f'Update {update} caused error {context.error}')

def main():

    print('Starting bot...')
    app = Application.builder().token(TOKEN).build()

    job_queue = JobQueue()
    job_queue.set_application(app)
    job_queue.run_repeating(continuous_data_processing, interval=60, first=0)

    # Commands
    app.add_handler(CommandHandler('start', start_command))
    app.add_handler(CommandHandler('help', help_command))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Errors
    app.add_error_handler(error)

    print('Polling...')
    app.run_polling()

if __name__ == "__main__":
    main()
