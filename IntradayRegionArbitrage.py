import numpy as np
from datetime import time


class IntradayRegionArbitrage:

    def __init__(self, bal: float, min_deviation: float, sl_percent: float, trigger_range: float, trade_size: float,
                 trade_size_percent: bool = False):
        assert min_deviation > 0, "min_deviation must be greater than 0"
        assert sl_percent > 0, "stop loss cant be 0 or negative"
        assert min_deviation > trigger_range > 0, "trigger range must be greater tah 0 and smaller than min_deviation"
        assert (trade_size < 1 if trade_size_percent else True), "Trade size must be smaller than 1, if it is a percentage!"


        """ Trading Params """
        self.min_deviation: float = min_deviation  # min deviation for arbitrage to trigger
        self.sl_percent: float = sl_percent  # stop-loss size
        self.trigger_range: float = trigger_range  # range of trade exit -> positive value only
        self.trade_size_percent: bool = trade_size_percent # if trade size is a percentage
        self.trade_size: float = trade_size

        """ Stored Values """
        self.balance: float = bal  # balance of portfolio
        self.tickers: list = []
        self.base_ticker: str = ""
        self.trades = []  # returns of individual trades
        self.shares: dict = {}  # shares of the arbitrage tickers
        self.base_shares: dict = {}  # shares of the base ticker by arbitrage ticker

        """ Internal Only/ Temporary Data """
        self._price_data: list = []
        self._base_share_price: float = 0
        self._cpt: list = []  # current position tickers

    def data_feed(self, timestamp: time, return_data: list, price_data: list, tickers: list):
        """
        :param timestamp: current time as datetime.time object
        :param return_data: list of return normalized to the base symbol
        :param price_data: list of price data including the base symbol on index 0
        :param tickers: list of tickers excluding the base symbol
        :return: void
        """

        assert len(tickers[1:]) == len(return_data), "Tickers and Data length dont match"
        assert len(tickers) == len(price_data), "Tickers and Price length dont match"

        self.base_ticker, self.tickers = tickers[0], tickers[1:]
        self._base_share_price = price_data[0]
        self._price_data = price_data[1:]

        is_closing = self.is_closing(timestamp)
        in_trade = len(self._cpt) > 0
        if in_trade:
            self.price_check(return_data)
            if is_closing:
                print(f'\tMarket-Closing --> close Trades')
                tmp = self._cpt
                _ = [self.close_trade(i) for i in tmp]
                print(f'{" Market-Closing ":#^100}')

        elif (not in_trade) and (not is_closing):
            opportunity, signal = self.check_opportunity(return_data)
            self._cpt = np.where(opportunity)[0].tolist()
            if len(self._cpt) > 0:
                self.trade_signal(signal)

    def check_opportunity(self, return_data: list) -> (list, list):
        """
        :param return_data: list of returns, normalized to the base symbol
        :return: opportunity: list of boolean, signal: list of boolean

        opportunity: weather the current data allows trade => threshold met
        signal: if the trade is short:False / long:True
        """
        opportunity, signal = [], []
        for data_point in return_data:
            opportunity.append(data_point > self.min_deviation)
            signal.append(data_point > 0)
        return opportunity, signal

    def trade_signal(self, signal: list):
        """
        :param signal: list of boolean, signals to be traded -> long/short
        :return:

        executes trades according to the signal
        """

        print(f"\t--Opening Trade")
        order_size = (self.trade_size * self.balance if self.trade_size_percent else self.trade_size) / len(self._cpt) * 2
        for idx in self._cpt:
            ticker = self.tickers[idx]
            price = self._price_data[idx]

            self.shares[ticker] = order_size / price * (1 if signal[idx] else -1)
            self.base_shares[ticker] = order_size / self._base_share_price * (-1 if signal[idx] else 1)

            self.balance += self.shares[ticker] * price
            self.balance += self.base_shares[ticker] * self._base_share_price

            print(f"\t\tBaseShare {self.base_ticker}-> amt: {self.base_shares[ticker]:.4f} @{self._base_share_price:.4f} --> total: {self.base_shares[ticker] * self._base_share_price:.4f}")
            print(f"\t\tTicker {ticker}-> amt: {self.shares[ticker]:.4f} @{price:.4f} --> total: {self.shares[ticker] * price:.4f}")

    def price_check(self, return_data: list):
        """
        :param return_data: list of returns, normalized to the base symbol
        :return: void

        checks whether current return meets take profit requirement
        checks whether current price meets stop loss requirements
        """
        for i in self._cpt:
            # trigger take profit
            if (return_data[i] <= self.trigger_range) and (return_data[i] >= -self.trigger_range):
                print("\ttake profit")
                self.close_trade(i)
                break

            # trigger stop-loss
            ticker: str = self.tickers[i]
            pnl = (self.balance + (self.base_shares[ticker] * self._base_share_price * -1) + (self.shares[ticker] * self._price_data[i] * -1))/self.balance - 1
            if pnl < (self.sl_percent * -1):
                print("\tstop loss")
                self.close_trade(i)

    def close_trade(self, idx: int):
        """
        :param idx: index of trade to be closed
        :return: void

        closing a trade and printing PNL
        """
        ticker: str = self.tickers[idx]
        tmp_bal: float = self.balance

        self.balance += (self.base_shares[ticker] * self._base_share_price * -1) + (self.shares[ticker] * self._price_data[idx] * -1)

        roi: float = self.balance / tmp_bal - 1

        print(f"\t--Closing Trade")
        print(f"\t\tBaseShare {self.base_ticker}-> amt: {-self.base_shares[ticker]:.4f} @{self._base_share_price:.4f} --> total: {-self.base_shares[ticker] * self._base_share_price:.4f}")
        print(f"\t\tTicker {ticker}-> amt: {-self.shares[ticker]:.4f} @{self._price_data[idx]:.4f} --> total: {-self.shares[ticker] * self._price_data[idx]:.4f}")
        print(f"\t PNL: {roi:.4%}")

        del self.shares[ticker]
        del self.base_shares[ticker]

        self.trades.append(roi)
        self._cpt.remove(idx)

    def is_closing(self, timestamp: time) -> bool:
        """
        :param timestamp: current time in datetime.time object
        :return: void

        checks whether market is closing: 16:30:00
        """
        return timestamp > time(16, 29, 0)
