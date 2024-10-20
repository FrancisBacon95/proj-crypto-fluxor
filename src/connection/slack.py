#-*-coding: utf-8-*-
import logging
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from src.config.env import SLACK_BOT_TOKEN, SLACK_CHANNEL_ID

logger = logging.getLogger(__name__)

class SlackClient():
    client = WebClient(token=SLACK_BOT_TOKEN, timeout=90)
    def upload_files(self, file: str, msg: str=None):
        # ID of channel that you want to upload file to
        try:
            # Call the files.upload method using the WebClient
            # Uploading files requires the `files:write` scope
            result = self.client.files_upload_v2(
                channels=SLACK_CHANNEL_ID,
                initial_comment=msg,
                file=file,
            )
            # Log the result
            logger.info(result)

        except SlackApiError as e:
            logger.error("Error uploading file: {}".format(e))
            