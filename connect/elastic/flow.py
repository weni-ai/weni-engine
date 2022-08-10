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

    def get_contact_detailed(self, flow_id: int, before: str, after: str):
        index = "contacts"
        before, after = es_convert_datetime(before, after)

        qs = Q(
            'bool', must=[Q('match', is_active='true') & Q('match', org_id=flow_id)]) \
            & Q(
            "range", last_seen_on={
                "gte": str(after),
                "lte": str(before)}
        )

        contacts = Search(using=self.client, index=index).query(qs)
        response = contacts.scan()
        return response

    def get_paginated_contacts(self, flow_id: int, before: str, after: str, scroll_id: str = None):
        before, after = es_convert_datetime(before, after)

        if scroll_id:
            page = self.client.scroll(scroll_id=scroll_id, scroll='1m')
            return page['hits']['hits']

        query = {
            "query": {
                "bool": {
                    "must": [
                        {
                            "match": {
                                "org_id": f"{flow_id}"
                            },
                        },
                        {
                            "match": {
                                "is_active": "true",
                            }
                        },
                        {
                            "range": {
                                "last_seen_on": {
                                    "gte": str(after),
                                    "lte": str(before)
                                }
                            }
                        }
                    ]
                }
            }
        }

        page = self.client.search(index="contacts", body=query, scroll=settings.SCROLL_KEEP_ALIVE, size=settings.SCROLL_SIZE)
        scroll_id = page["_scroll_id"]
        scroll_size = page["hits"]["total"]["value"]
        hits = page["hits"]["hits"]
        scroll = {
            "scroll_id": scroll_id,
            "scroll_size": scroll_size
        }
        return scroll, hits

    def clear_scroll(self, scroll_id):
        self.client.clear_scroll(scroll_id=scroll_id)
