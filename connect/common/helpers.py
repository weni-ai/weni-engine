import logging
import pendulum
import psycopg2
from django.conf import settings
from django.core.mail import get_connection, EmailMultiAlternatives

logger = logging.getLogger(__name__)


def send_mass_html_mail(datatuple, fail_silently=False, user=None, password=None,
                        connection=None):
    """
    Given a datatuple of (subject, text_content, html_content, from_email,
    recipient_list), sends each message to each recipient list. Returns the
    number of emails sent.

    If from_email is None, the DEFAULT_FROM_EMAIL setting is used.
    If auth_user and auth_password are set, they're used to log in.
    If auth_user is None, the EMAIL_HOST_USER setting is used.
    If auth_password is None, the EMAIL_HOST_PASSWORD setting is used.

    """
    connection = connection or get_connection(
        username=user, password=password, fail_silently=fail_silently)
    messages = []
    for subject, text, html, from_email, recipient in datatuple:
        message = EmailMultiAlternatives(subject, text, from_email, recipient)
        message.attach_alternative(html, 'text/html')
        messages.append(message)
    return connection.send_messages(messages)


class KeycloakCleanup:

    dbname = settings.KC_DB_NAME
    user = settings.KC_DB_USER
    password = settings.KC_DB_PASSWORD
    host = settings.KC_DB_HOST
    port = settings.KC_DB_PORT
    realm_id = settings.OIDC_RP_REALM_NAME

    def __init__(self):
        self.conn = self.connection()
        self.cur = self.cursor()

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

    def fetch(self) -> tuple((int, list)):

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
