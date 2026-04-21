import numpy as np
import pandas as pd

from crypto_bot.ml.filter import MLFilterConfig, MLFilterModel


def test_ml_shadow_always_allows():
    class FakePipe:
        def predict_proba(self, X):
            return np.array([[0.1, 0.9]])

    m = MLFilterModel(FakePipe(), MLFilterConfig(min_proba=0.99, shadow=True))
    feats = pd.DataFrame(
        [{"ema_ratio": 0.0, "rsi": 50.0, "atr_pct": 0.01}],
    )
    ok, p = m.allow(feats)
    assert ok is True
    assert p == 0.9
