from elasticsearch import Elasticsearch
from elasticsearch_dsl import Search, Q
from connect.elastic.elastic import ElasticHandler
from connect.utils import es_convert_datetime
from django.conf import settings


class ElasticFlow(ElasticHandler):
    base_url = settings.FLOWS_ELASTIC_URL
    client = Elasticsearch(f"{base_url}")

    def __init__(self) -> None:
        super().__init__()

    def get_contact_detailed(self, before: str, after: str):
        index = "contacts"
        before, after = es_convert_datetime(before, after)

        qs = Q(
            'bool', must=[Q('match', is_active='true')]) \
            & Q(
            "range", last_seen_on={
                "gte": str(after),
                "lt": str(before)}
        )

        contacts = Search(using=self.client, index=index).query(qs)
        response = contacts.execute()
        return response
