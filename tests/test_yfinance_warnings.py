import warnings

import pytest

from qrl.data import silence_yfinance_inplace_warnings

yf_utils = pytest.importorskip("yfinance.utils")

_QUOTE = {
    "timestamp": [2, 1],
    "indicators": {
        "quote": [
            {
                "volume": [1, 2],
                "open": [1.0, 2.0],
                "close": [1.0, 2.0],
                "low": [1.0, 2.0],
                "high": [1.0, 2.0],
            }
        ]
    },
}


def _record_parse_quotes_warnings(silence: bool) -> list[warnings.WarningMessage]:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        if silence:
            silence_yfinance_inplace_warnings()
        yf_utils.parse_quotes(_QUOTE)
    return caught


def test_yfinance_inplace_warning_is_hidden_by_the_helper():
    assert _record_parse_quotes_warnings(silence=True) == []


def test_helper_hides_only_yfinance_inplace_warnings():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        silence_yfinance_inplace_warnings()
        warnings.warn("unrelated deprecation", DeprecationWarning, stacklevel=1)
        warnings.warn("inplace keyword is deprecated", FutureWarning, stacklevel=1)
    assert [str(w.message) for w in caught] == [
        "unrelated deprecation",
        "inplace keyword is deprecated",
    ]
