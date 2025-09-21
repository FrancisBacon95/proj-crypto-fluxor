# 서버 테스트용 파일 - 모든 로직 비활성화
import logging
from datetime import datetime

import pytz

from src.connection.slack import SlackClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
kst = pytz.timezone("Asia/Seoul")


def send_test_message():
    """서버 테스트 메시지를 슬랙으로 전송"""
    current_time = datetime.now(tz=kst).strftime("%Y-%m-%d %H:%M:%S")
    title = "🧪[서버 테스트 중]🧪"
    contents = (
        f"*시간*: `{current_time}`\n*메시지*: `모든 투자 로직이 비활성화되어 있습니다.`"
    )
    SlackClient().chat_postMessage(title, contents)
    logger.info(f"서버 테스트 메시지 전송 완료: {current_time}")
    return {"status": "test_message_sent", "time": current_time}


if __name__ == "__main__":
    send_test_message()
