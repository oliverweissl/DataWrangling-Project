import numpy as np
from datetime import time


class IntradayRegionArbitrage:

    def __init__(self, bal: float, min_deviation: float, sl_percent: float, trigger_range: float, trade_size: float,
                 trade_size_percent: bool = False):
        self.balance = bal  # balance of portfolio
        self.min_deviation = min_deviation  # min deviation for arbitrage to trigger
        self.sl_percent = sl_percent  # stop-loss size
        self.trigger_range = trigger_range  # range of trade exit -> positive value only
        assert (trade_size < 1 if trade_size_percent else True),\
            "Trade size must be smaller than 1, if it is a percentage!"
        self.trade_size_percent = trade_size_percent
        self.trade_size = trade_size

        self.in_trade: bool = False
        self.shares: dict = {}  # shares of the arbitrage tickers
        self.base_shares: dict = {}  # shares of the base ticker by arbitrage ticker

        self._tickers: list = []
        self._price_data: list = []
        self.cpt: list = []  # current position tickers

    def data_feed(self, timestamp: time, return_data: list, price_data: list, tickers: list):
        self._price_data = price_data

        is_closing = self.is_closing(timestamp)

        if self.in_trade:
            self.price_check(return_data)
            if is_closing:
                self.close_trades()
        elif (not self.in_trade) and (not is_closing):
            opportunity, signal = self.check_opportunity(return_data)
            self._tickers = [tickers[i+1] for i in np.where(opportunity)[0].tolist()]  # +1 because tickers has base ticker in it
            if len(signal := [signal[i] for i in np.where(opportunity)[0].tolist()]) > 0:
                self.trade_signal(signal)



    def check_opportunity(self, return_data: list) -> (list, list):
        opportunity, signal = [], []
        for dp in return_data:
            opportunity.append(dp > self.min_deviation)
            signal.append(dp > 0)
        return opportunity, signal

    def trade_signal(self, signal: list):
        order_size = (self.trade_size * self.balance if self.trade_size_percent else self.trade_size) / len(signal) * 2
        for i, ticker in enumerate(self._tickers):
            self.shares[ticker] = order_size / self._price_data[i] * (1 if signal[i] else -1)
            self.base_shares[ticker] = order_size / self._price_data[0] * (-1 if signal[i] else 1)
        self.in_trade = True

    def price_check(self, return_data: list):
        for i, ticker in enumerate(self._tickers):
            # trigger take profit
            if (return_data[i] <= self.trigger_range) and (return_data[i] >= -self.trigger_range):
                self.close_trade(i, ticker)
                break

            # trigger stop-loss
            pnl = self.shares[ticker] * self._price_data[i] + self.base_shares[ticker] * self._price_data[0]
            if pnl < (self.trade_size / len(self._tickers) * self.sl_percent * -1):
                self.close_trade(i, ticker)


    def close_trade(self, i: int, ticker: str):
        self.balance += self.base_shares[ticker] * self._price_data[0]
        self.balance += self.shares[ticker] * self._price_data[i]

        del self.shares[ticker]
        del self.base_shares[ticker]
        self._tickers.remove(ticker)


        if len(self._tickers) < 1:
            self.in_trade = False


    def close_trades(self):
        [self.close_trade(i, ticker) for i, ticker in enumerate(self._tickers)]

    def is_closing(self, timestamp: time) -> bool:
        return timestamp > time(16, 28, 0)