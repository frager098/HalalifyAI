"""Validate numeric bars without downloading data or assuming action quality."""
import numpy as np
import pandas as pd


def validate(frame):
    if frame.empty:
        raise ValueError('No bars returned')
    if frame.duplicated(['ticker', 'session_date']).any():
        raise ValueError('Duplicate sessions returned')
    columns = ['open', 'high', 'low', 'close', 'volume']
    values = frame[columns].apply(pd.to_numeric, errors='raise')
    if not np.isfinite(values).all().all():
        raise ValueError('Nonfinite price/volume')
    if (values[['open', 'high', 'low', 'close']] <= 0).any().any() or (values.volume < 0).any():
        raise ValueError('Invalid price/volume')
    if ((values.high < values[['open', 'close', 'low']].max(axis=1)) |
            (values.low > values[['open', 'close', 'high']].min(axis=1))).any():
        raise ValueError('Invalid OHLC values')
