'''
WARNING: The below strategy is a sample and you might lose money, use at your own risk
'''
import time, datetime, logging, numpy, talib, math
from binance import ThreadedWebsocketManager
from binance.client import Client
from binance.enums import *

formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')

def setup_logger(name, log_file, level):
    """To setup as many loggers as you want"""
    handler = logging.FileHandler(log_file)        
    handler.setFormatter(formatter)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    return logger

logger_bot = setup_logger('first_logger', 'logger_bot.log', logging.INFO)

# Insert your own api_key and api_secret from your Binance account
api_key = "insert your api_key here"
api_secret = "insert your api_secret here"

# Initialisation of global variables
record = True
record_time = datetime.datetime.now()
initialisation_30s = record_time + datetime.timedelta(seconds=30)
initialisation_phase = True
ticker_dict = {}
streams = ['!ticker@arr']
position_symbol = ''
closes = []
in_position = False
BOUGHT_PRICE = 0
SOLD_PRICE = 0
TRADE_QUANTITY = 0
SELL_QUANTITY = 0
BUY_QUANTITY = 0
BOUGHT_AMT = 0
SOLD_AMT = 0
ESTIMATED_EXECUTED_BOUGHT_PRICE = 0
ESTIMATED_EXECUTED_SOLD_PRICE = 0
acc_profit = 0
same_min = False

# Amount of USDT you want to trade with
USDT_AMOUNT = 100

client = Client(api_key, api_secret)

now = datetime.datetime.now()
logger_bot.info(f'{now:%Y-%m-%d %H:%M:%S} connection opened')

# Function to place market order
def order(side, quantity, symbol,order_type=ORDER_TYPE_MARKET):
    global SELL_QUANTITY, BOUGHT_AMT, SOLD_AMT, ESTIMATED_EXECUTED_BOUGHT_PRICE, ESTIMATED_EXECUTED_SOLD_PRICE
    try:
        order = client.create_order(symbol=symbol, side=side, type=order_type, quantity=quantity)
        logger_bot.info(order)
        if side == SIDE_BUY:
            # Ensure sufficient BNB to pay commission fees
            SELL_QUANTITY = float(order["executedQty"])
            BOUGHT_AMT = float(order["cummulativeQuoteQty"])
            ESTIMATED_EXECUTED_BOUGHT_PRICE = BOUGHT_AMT/SELL_QUANTITY
        else:
            SOLD_AMT = float(order["cummulativeQuoteQty"])
            ESTIMATED_EXECUTED_SOLD_PRICE = SOLD_AMT/SELL_QUANTITY
    except Exception as e:
        logger_bot.info("an exception occured - {}".format(e))
        return False
    return True

def main():
    twm = ThreadedWebsocketManager(api_key=api_key, api_secret=api_secret)

    # start is required to initialise its internal loop
    twm.start()

    # Constants
    # Filter away symbols with price greater than PRICE_LIMIT
    PRICE_LIMIT = 5
    # Add symbols to exclude from trading here:
    exclusion_usdt_symbols = ["BUSDUSDT", "USDCUSDT", "TUSDUSDT", "SUSDUSDT","PAXUSDT"]
    # Determine moving average periods to compare for when to sell
    FAST_CLOSES_MA_PERIOD = 8
    SLOW_CLOSES_MA_PERIOD = 20

    # this function is entered whenever streaming data is received
    def handle_socket_message(msg):
        global record, record_time, initialisation_phase, initialisation_30s, ticker_dict, streams, position_symbol, closes, in_position, BOUGHT_PRICE, SOLD_PRICE, TRADE_QUANTITY, SELL_QUANTITY, BUY_QUANTITY, BOUGHT_AMT, SOLD_AMT, ESTIMATED_EXECUTED_BOUGHT_PRICE, ESTIMATED_EXECUTED_SOLD_PRICE, USDT_AMOUNT, acc_profit,same_min
        
        # check for new tickers once everyday
        now = datetime.datetime.now()
        if record_time.day != now.day:
            record = True
            initialisation_phase True
            record_time = datetime.datetime.now()
            initialisation_30s = record_time + datetime.timedelta(seconds=30)

        # Allow 30 seconds to initialise desired symbols into a dictionary
        if now>initialisation_30s and initialisation_phase:
            initialisation_phase = False
            record = False

        # Record desired symbols from '!ticker@arr' stream into dictionary and open socket for each symbol to receive 1 min candlestick data
        if msg['stream'] == '!ticker@arr' and record and not in_position:
            # Reset streams variable to prevent double streaming of the same stream
            streams = []
            for ticker in msg['data']:
                symbol = ticker["s"]
                price = float(ticker["c"])
                # Filter and store desired symbols
                if symbol.endswith('USDT') and not symbol.endswith('UPUSDT') and not symbol.endswith('DOWNUSDT') and (symbol not in exclusion_usdt_symbols) and price<PRICE_LIMIT:
                    if symbol not in ticker_dict:
                        ticker_dict[symbol]= {'VOL':float('inf'),'CH':float('inf'),'CLOSE':float('inf')}
                        stream_string = symbol.lower()+"@kline_1m"
                        streams.append(stream_string)
            if len(streams) != 0:
                twm.start_multiplex_socket(callback=handle_socket_message, streams=streams)
                now = datetime.datetime.now()
                logger_bot.info(f'{now:%Y-%m-%d %H:%M:%S} ticker streams added {streams}')

        # Run the following when candlestick data is received for desired symbols 
        if msg['stream'] != '!ticker@arr':
            candle = msg['data']['k']
            is_candle_closed = candle['x']
            sym = candle['s']
            close_price = float(candle['c'])
            open_price = float(candle['o'])
            low_price = float(candle['l'])
            price_change = ((close_price - open_price)/open_price)*100
            volume = float(candle['v'])
            time = int(candle['t']) / 1000
            timevalue = datetime.datetime.fromtimestamp(time)
            if ticker_dict[sym]['VOL'] == 0:
                vol_ratio = 0
            else:
                vol_ratio = volume/ticker_dict[sym]['VOL']
            if ticker_dict[sym]['CH'] == 0:
                change_ratio = 0
            else:
                change_ratio = abs(price_change/ticker_dict[sym]['CH'])
           
            # Determine criteria to buy here:
            if vol_ratio>300 and volume>300000 and price_change>5 and not in_position and not same_min:
                BUY_QUANTITY = math.floor(USDT_AMOUNT/close_price)
                order_succeeded = order(SIDE_BUY, BUY_QUANTITY, sym)
                if order_succeeded:
                    in_position = True
                    same_min = True
                    position_symbol = sym
                    # Use the previous candlestick as moving average reference for rough estimation (not correct in reality)
                    closes = [ticker_dict[sym]['CLOSE']]*20
                    logger_bot.info(f"{timevalue:%Y-%m-%d %H:%M:%S} Symbol {position_symbol} Volume {volume:.0f} Change {price_change:.2f}% VolRatio {vol_ratio:.0f} ChangeRatio {change_ratio:.1f} Bought for {ESTIMATED_EXECUTED_BOUGHT_PRICE:.6f} with {BOUGHT_AMT:.2f}")

            # Run the following when 1 min candlestick is closed for every symbol
            if is_candle_closed:
                if msg['stream'] == (position_symbol.lower()+'@kline_1m') and in_position:
                    # Update the list of close prices for in_position symbol
                    closes.pop(0)
                    closes.append(close_price)
                    # Calculate the two moving averages
                    fast_closes_ma = sum(closes[12:])/8
                    slow_closes_ma = sum(closes)/20
                    logger_bot.info(f"{timevalue:%Y-%m-%d %H:%M:%S} Symbol {sym} Close {close_price:.6f} 8MA {fast_closes_ma:.6f} 20MA {slow_closes_ma:.6f}")
                    # Determine criteria to sell here:
                    if fast_closes_ma <= slow_closes_ma:
                        order_succeeded = order(SIDE_SELL, SELL_QUANTITY, position_symbol)
                        if order_succeeded:
                            in_position = False
                            profit = SOLD_AMT - BOUGHT_AMT
                            spread = ESTIMATED_EXECUTED_SOLD_PRICE - ESTIMATED_EXECUTED_BOUGHT_PRICE
                            acc_profit += profit
                            logger_bot.info(f"{timevalue:%Y-%m-%d %H:%M:%S} Strategy {strategy} Sold for {ESTIMATED_EXECUTED_SOLD_PRICE:.6f} with {SOLD_AMT:.2f} Spread: {spread:.6f} Profit(USDT): {profit:.6f} Acc_Profit: {acc_profit:.6f}")
                # Update dictionary with the latest 1 min candlestick data
                ticker_dict[sym]['VOL']=volume
                ticker_dict[sym]['CH']=price_change
                ticker_dict[sym]['CLOSE']=close_price
                same_min = False

    #start the multiplex socket
    twm.start_multiplex_socket(callback=handle_socket_message, streams=streams)

    twm.join()

if __name__ == "__main__":
   main()