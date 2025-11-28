import time

from pika.exceptions import AMQPConnectionError, AMQPChannelError

from connect.internals.event_driven.connection.rabbitmq import RabbitMQConnection


class PikaConnectionBackend:
    _start_message = "[+] Connection established. Waiting for events"

    def __init__(self, handle_consumers: callable):
        self._handle_consumers = handle_consumers
        self.rabbitmq_instance = RabbitMQConnection()

    def start_consuming(self):
        while True:
            try:
                # Ensure connection is open
                if not self.rabbitmq_instance.make_connection():
                    self.rabbitmq_instance._establish_connection()

                channel = self.rabbitmq_instance.channel

                # Register consumers
                self._handle_consumers(channel)

                print(self._start_message)

                # Start consuming (blocking call)
                channel.start_consuming()

            except (
                AMQPConnectionError,
                AMQPChannelError,
                ConnectionRefusedError,
                OSError,
            ) as error:
                print(f"[-] Connection error: {error}")
                print("    [+] Reconnecting in 5 seconds...")
                time.sleep(5)
                self.rabbitmq_instance._establish_connection()
            except KeyboardInterrupt:
                print("\n[!] Consumer stopped by user")
                if hasattr(self.rabbitmq_instance, "connection"):
                    self.rabbitmq_instance.connection.close()
                break
            except Exception as error:
                # TODO: Handle exceptions with RabbitMQ
                print("error on start_consuming:", type(error), error)
                time.sleep(5)
                self.rabbitmq_instance._establish_connection()
