import logging

from connect.celery import app
from connect.authentication.models import User

logger = logging.getLogger(__name__)


@app.task(name="send_user_flow_info", ignore_result=True)
def send_user_flow_info(
    flow_data: dict,
    user_email: str,
) -> bool:
    try:
        user = User.objects.get(email=user_email)
        user.send_request_flow_user_info(flow_data=flow_data)
        return True
    except Exception as e:
        logger.error(e)
        return False
