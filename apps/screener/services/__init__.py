"""
Screener service package — wraps the ported Flask backend modules
(indicators/, advanced_strategies/, trading_analysis/, trade_analyzer.py).

The submodules use flat top-level imports (e.g. `from complete_indicators import ...`)
because they were originally a Flask app where `sys.path` included the indicators
directory. We replicate that by inserting both this directory and the indicators
sub-package onto `sys.path` at import time.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_INDICATORS = os.path.join(_HERE, "indicators")

for _p in (_HERE, _INDICATORS):
    if _p not in sys.path:
        sys.path.insert(0, _p)
