import os
from pathlib import Path

KIS_API_AUTH_PATH = os.getenv("KIS_API_AUTH_PATH")
BITHUMB_KEY = os.getenv("BITHUMB_KEY")
BITHUMB_SECRET = os.getenv("BITHUMB_SECRET")
COINMARKETCAP_KEY = os.getenv("COINMARKETCAP_KEY")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent 
