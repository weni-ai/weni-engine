from abc import ABCMeta
import logging
logger = logging.getLogger(__name__)


class ElasticHandler(metaclass=ABCMeta):  # pragma: no cover
    """
    ElasticHandler is our abstract base type for custom elastic search connection providers. Each provider will
    a way to connect to connect with your service to return information remotely
    """

    def get_contact_detailed(self):
        raise NotImplementedError()
