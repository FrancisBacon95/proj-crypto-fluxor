import logging
import os
from datetime import datetime

import pytz

# 로그 레벨 설정 (기본: INFO)
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# KST 시간대 설정
kst = pytz.timezone("Asia/Seoul")


class KSTFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        # UTC 시간을 KST로 변환
        dt = datetime.fromtimestamp(record.created, tz=kst)
        if datefmt:
            s = dt.strftime(datefmt)
        else:
            s = dt.strftime("%Y-%m-%d %H:%M:%S KST")
        return s


# 로깅 포맷 설정 (파일명과 라인 번호 포함)
LOG_FORMAT = (
    "%(asctime)s - %(filename)s:%(lineno)d - %(name)s - %(levelname)s - %(message)s"
)


def get_logger(name: str) -> logging.Logger:
    # 로거 생성
    logger = logging.getLogger(name)
    logger.setLevel(LOG_LEVEL)

    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler()
    console_handler.setLevel(LOG_LEVEL)

    # KST 포맷터 사용
    formatter = KSTFormatter(LOG_FORMAT)
    console_handler.setFormatter(formatter)

    # 핸들러가 없는 경우 추가 (중복 방지)
    if not logger.hasHandlers():
        logger.addHandler(console_handler)

    return logger
