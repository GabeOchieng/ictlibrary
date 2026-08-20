"""Data sources for the ICT library: OANDA (live/practice) and CSV."""

from .csv_loader import load_csv, save_csv

__all__ = ["load_csv", "save_csv", "OandaClient", "OandaError",
           "AlpacaClient", "AlpacaError"]


def __getattr__(name):
    # Import broker clients lazily so ``requests`` is only needed when used.
    if name in ("OandaClient", "OandaError"):
        from .oanda import OandaClient, OandaError
        return {"OandaClient": OandaClient, "OandaError": OandaError}[name]
    if name in ("AlpacaClient", "AlpacaError"):
        from .alpaca import AlpacaClient, AlpacaError
        return {"AlpacaClient": AlpacaClient, "AlpacaError": AlpacaError}[name]
    raise AttributeError(name)
