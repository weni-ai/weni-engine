import logging
from typing import Tuple

import pendulum
import psycopg2

from django.conf import settings


logger = logging.getLogger(__name__)


class KeycloakCleanup:

    def __init__(
            self,
            dbname: str = settings.KC_DB_NAME,
            user: str = settings.KC_DB_USER,
            password: str = settings.KC_DB_PASSWORD,
            host: str = settings.KC_DB_HOST,
            port: str = settings.KC_DB_PORT,
            realm_id: str = settings.OIDC_RP_REALM_NAME
    ):
        self.conn = self.connection()
        self.cur = self.cursor()
        self.dbname = dbname
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.realm_id = realm_id

    def connection(self):
        try:
            conn = psycopg2.connect(dbname=self.dbname, user=self.user, password=self.password, host=self.host, port=self.port)
            return conn
        except psycopg2.OperationalError as error:
            logger.error(error)
            return False

    def cursor(self):
        if self.conn:
            cur = self.conn.cursor()
            return cur

    def fetch(self) -> Tuple[int, list]:

        event_time = pendulum.now().end_of("day").timestamp() * 1000

        self.cur.execute(f"SELECT * FROM event_entity WHERE realm_id='{self.realm_id}' AND event_time < {event_time}")
        results = self.cur.fetchall()
        print(len(results))
        return len(results), results

    def delete(self, event_time=None) -> None:
        if not event_time:
            time = pendulum.now().end_of("day")
            event_time = time.timestamp() * 1000

        query = f"DELETE FROM event_entity WHERE realm_id='{self.realm_id}' AND event_time < {event_time}"

        print(f"{query} ({time})")

        self.cur.execute(query)
        self.conn.commit()

    def vacuum(self) -> None:

        self.conn.autocommit = True
        cur = self.cur

        query = "VACUUM FULL VERBOSE event_entity;"

        print(query)

        cur.execute(query)

        self.close_connection()

    def close_connection(self) -> None:
        self.cur.close()
        self.conn.close()
