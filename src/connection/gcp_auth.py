from datetime import datetime
import pytz
import pandas as pd
import gspread
from google.auth import default
from google.oauth2.service_account import Credentials
from src.config.env import GCP_KEY_PATH, EXECUTE_ENV, PROJ_ID

class GCPAuth():
    def __init__(self, scope=None) -> None:
        self.scope = scope
        # 로컬 환경에서는 JSON 키 파일을 사용하고, Cloud Run에서는 기본 자격 증명을 사용
        if EXECUTE_ENV == 'LOCAL':
            # 키 파일 경로가 제공되면 키 파일을 사용한 인증
            self.credential = Credentials.from_service_account_file(GCP_KEY_PATH, scopes=self.scope)
        else:
            #  키 파일 없이 기본 자격 증명 (ADC)을 사용
            self.credential, _ = default(scopes=self.scope, quota_project_id=PROJ_ID)
        self.project_id = PROJ_ID
