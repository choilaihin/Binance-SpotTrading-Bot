# Binance-SpotTrading-Bot

A bot for trading cryptocurrencies in Binance's spot markets

## Description

This bot places Binance spot market order when 1 minute candlestick volume and price is spiking and sell when 8 period moving average crosses below the 20 period moving average.

WARNING: This strategy is a sample and you might lose money, use at your own risk

## Technologies Used

- Using python-binance ThreadedWebsocketManager Websocket
  https://python-binance.readthedocs.io/en/latest/index.html

- Parsing candlestick data
  https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md#individual-symbol-ticker-streams
