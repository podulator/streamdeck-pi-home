from ..IScroller import IScroller
from datetime import datetime
from decimal import Decimal, Context
from requests_cache import CachedSession
from typing import Dict

import yfinance as yf
from datetime import timedelta

class StocksScroller(IScroller):

    cache_name : str = "streamdeck_cache"
    cache_time : int = 300

    def __init__(self, app, config, font) -> None:
        super().__init__(app, config, font)
        self._pages: list[str] = []
        self._page_counter: int = 0

    def generate(self) -> bytes:

        self._page_counter = 0
        self._pages.clear()

        prices : list[Dict] = self._get_prices(self._config["symbols"])
        for p in prices:
            now : str = p.get("timestamp")
            price : Decimal = p.get("price")
            currency : str = p.get("currency")
            stock_name : str = p.get("name")
            stock_symbol : str = p.get("symbol")
            change : int = p.get("change")
            change_symbol = "+" if change >= 0 else ""
            self._pages.append(
                f'{stock_name} - ({stock_symbol})\n{currency} {price}\n{change_symbol}{change}% today at {now}'
            )

        if self.has_next:
            return self.next()
        return None

    def deactivate(self):
        pass

    def _get_prices(self, symbols : list[Dict]) -> list[Dict]:

        expire : timedelta = timedelta(seconds = StocksScroller.cache_time)
        with CachedSession(cache_name = StocksScroller.cache_name, expire_after = expire) as sess: 
            sess.headers['User-agent'] = f"{StocksScroller.cache_name}/1.0"
            symbols_str : list[str] = [ d.get("symbol") for d in  symbols]
            symbol_list : str = ' '.join(symbols_str).replace(".", "-")
            response = yf.Tickers(tickers = symbol_list, session = sess)
            now : str = datetime.now().strftime("%H:%M")
            results : list[Dict] = []
            for sy in symbols:
                try:
                    symbol : str = sy.get("symbol")
                    name : str = sy.get("name")
                    ticker : yf.Ticker = response.tickers[symbol]
                    if not ticker:
                        continue
                    price : Decimal = Context(prec=6).create_decimal(ticker.info["currentPrice"]).quantize(Decimal("0.00"))
                    open : Decimal = Context(prec=6).create_decimal(ticker.info["open"]).quantize(Decimal("0.00"))
                    currency_str : str = response.tickers[symbol].info["currency"]
                    match currency_str:
                        case "USD":
                            currency = "$"
                        case "EUR":
                            currency = "€"
                        case "GBP":
                            currency = "£"
                        case _:
                            currency = "?"

                    change_f : float = (price / open * 100) - 100
                    change : Decimal = Context(prec=2).create_decimal(change_f).quantize(Decimal("0.00"))
                    results.append({
                        "name" : name,
                        "symbol" : symbol, 
                        "price": price,
                        "currency": currency,
                        "change": change,
                        "timestamp": now
                        }
                    )
                except Exception as ex:
                    self._log.error(ex)
                    pass
            return results
    