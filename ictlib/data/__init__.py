"""Data sources for the ICT library: OANDA (live/practice) and CSV."""

from .csv_loader import load_csv, save_csv

__all__ = ["load_csv", "save_csv", "OandaClient", "OandaError"]


def __getattr__(name):
    # Import OANDA lazily so ``requests`` is only needed when actually used.
    if name in ("OandaClient", "OandaError"):
        from .oanda import OandaClient, OandaError
        return {"OandaClient": OandaClient, "OandaError": OandaError}[name]
    raise AttributeError(name)
