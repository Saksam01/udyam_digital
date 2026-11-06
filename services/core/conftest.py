"""Forces mock KYC mode and the fixed demo date for the test run."""

import os
import sys

os.environ.setdefault("ID_VALIDATION_MODE", "mock")
os.environ.setdefault("AS_OF_DATE", "2026-07-15")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
