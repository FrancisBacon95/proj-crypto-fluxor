import os
import dotenv
from pathlib import Path
dotenv.load_dotenv()

PROJ_ID = os.getenv("PROJ_ID")
EXECUTE_ENV = os.getenv("EXECUTE_ENV")
GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")
GOOGLE_SERVICE_ACCOUNT_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH", '')
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", '')
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", '')

BITHUMB_KEY = os.getenv("BITHUMB_KEY")
BITHUMB_SECRET = os.getenv("BITHUMB_SECRET")

BINANCE_KEY = os.getenv("BINANCE_KEY")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

COINMARKETCAP_KEY = os.getenv("COINMARKETCAP_KEY")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent 
GCP_KEY_PATH = GOOGLE_SERVICE_ACCOUNT_PATH