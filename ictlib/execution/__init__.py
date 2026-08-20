"""Execution layer — route scanner signals to a broker as bracket orders.

    from ictlib.execution import PaperBroker, Trader

    broker = PaperBroker(balance=10_000, pip=0.0001, pip_value=10)
    trader = Trader(broker, instrument="EUR_USD", pip=0.0001, dry_run=False)
    trader.process(signals)          # submit bracket orders
    for candle in live_feed:         # advance the paper simulation
        broker.feed(candle)
    print(broker.account())

Live brokers (OandaBroker, AlpacaBroker) are imported lazily so ``requests`` is
only needed when actually trading live.
"""

from .base import Broker, Account, OrderResult, BrokerOrder, Position
from .paper import PaperBroker
from .trader import Trader

__all__ = [
    "Broker", "Account", "OrderResult", "BrokerOrder", "Position",
    "PaperBroker", "Trader", "OandaBroker", "AlpacaBroker",
]


def __getattr__(name):
    if name == "OandaBroker":
        from .oanda_exec import OandaBroker
        return OandaBroker
    if name == "AlpacaBroker":
        from .alpaca_exec import AlpacaBroker
        return AlpacaBroker
    raise AttributeError(name)
