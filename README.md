# Crypto Trading Bot

![Python](https://img.shields.io/badge/Python-3.10-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Active-success)

A Python crypto trading bot using Binance API.

## Features
- EMA strategy
- MACD crossover
- RSI filter
- Volume confirmation
- Backtesting
- Telegram alerts
- Chart plotting

## Installation
pip install -r requirements.txt

## Run
python bot.py

## Configuration
Create a `.env` file:

BINANCE_API_KEY=your_key  
BINANCE_SECRET_KEY=your_secret  
TELEGRAM_TOKEN=your_token  
CHAT_ID=your_chat_id  

## Backtest Example
![Backtest Chart](logs/backtest_chart.png)