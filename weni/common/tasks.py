import requests

from weni.celery import app
from weni.common.models import Service


@app.task()
def status_service() -> None:
    def is_page_available(url: str, method_request: requests, **kwargs) -> bool:
        """This function retreives the status code of a website by requesting
        HEAD data from the host. This means that it only requests the headers.
        If the host cannot be reached or something else goes wrong, it returns
        False.
        """
        try:
            url = "https://" + url
            response = method_request(url=url, **kwargs)
            if int(response.status_code) == 200:
                return True
            return False
        except Exception:
            return False

    for service in Service.objects.all():
        service.status = is_page_available(
            url=service.url, method_request=requests.get, timeout=10
        )
        service.save(update_fields=["status"])
