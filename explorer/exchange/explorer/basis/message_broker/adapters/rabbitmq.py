import ssl
import threading
import time
import traceback
from threading import Thread
from typing import Optional, Dict

import pika
from django.conf import settings
from pika import spec
from pika.adapters.blocking_connection import BlockingChannel, BlockingConnection
from sentry_sdk import capture_exception

from exchange.explorer.basis.message_broker.adapters.rabbitmq_binding_config import RabbitmqBindingConfig
from exchange.explorer.basis.message_broker.errors.topic_subscriber_exist_error import TopicSubscriberExistError
from exchange.explorer.basis.message_broker.ports.message_broker_config import MessageBrokerConfig
from exchange.explorer.basis.message_broker.ports.message_broker_interface import MessageBrokerInterface
from exchange.explorer.basis.message_broker.ports.subscriber_interface import SubscriberInterface
from exchange.explorer.utils.logging import get_logger


class RabbitMQService(MessageBrokerInterface):
    PUBLIC_EXCHANGE = "public_exchange"

    logger = get_logger()

    def __init__(self, host: str, port: int, username: str, password: str, use_proxy: bool) -> None:
        self.connection_params = pika.ConnectionParameters(
            host=host,
            port=port,
            credentials=pika.PlainCredentials(
                username=username,
                password=password
            ),
            ssl_options=pika.SSLOptions(
                context=ssl.create_default_context(
                    cafile="./rabbitmq.crt"
                )
            ),
            socket_timeout=120,
            connection_attempts=12,
            heartbeat=300,
            retry_delay=5
        )

        self._subscribers: Dict[str, SubscriberInterface] = {}
        self._subscribers_connections: Dict[str, BlockingConnection] = {}
        self._threads: Dict[str, Thread] = {}
        self._monitor_thread: Thread
        self._connection: Optional[BlockingConnection] = None
        self._channel: Optional[BlockingChannel] = None
        self._use_proxy: bool = use_proxy

    def _create_connection(self) -> BlockingConnection:
        import socket
        original_socket = socket.socket

        def create_proxy_socket(*args, **kwargs):
            import socks

            s = socks.socksocket(*args, **kwargs)
            s.set_proxy(
                proxy_type=socks.SOCKS5,
                addr=settings.PROXY_HOST,
                port=settings.PROXY_PORT,
                username=None,
                password=None
            )
            return s

        if self._use_proxy:
            socket.socket = create_proxy_socket
        try:
            connection = BlockingConnection(self.connection_params)
        finally:
            socket.socket = original_socket
        return connection

    def _get_channel(self) -> BlockingChannel:
        if not self._connection or self._connection.is_closed:
            self._connection = self._create_connection()
        if not self._channel or self._channel.is_closed:
            self._channel = self._connection.channel()
        return self._channel

    def add_custom_config(self, *config: MessageBrokerConfig) -> None:
        for conf in config:
            if isinstance(conf, RabbitmqBindingConfig):
                self._create_queue(queue=conf.queue())
                self._get_channel().queue_bind(
                    exchange=self.PUBLIC_EXCHANGE,
                    queue=conf.queue(),
                    routing_key=conf.routing_key()
                )

    def _monitor_threads(self) -> None:
        try:
            while True:
                time.sleep(5)

                for queue, thread in self._threads.items():
                    if not thread.is_alive():
                        self._threads[queue] = self._create_and_start_consumer_thread(queue)
        except Exception as e:
            capture_exception(e)

        self._start_monitor_thread()

    def _create_queue(self, queue: str) -> None:
        self._get_channel().queue_declare(queue=queue, durable=True)

    def publish(self, topic: str, message: str) -> None:
        self._get_channel().basic_publish(
            exchange=self.PUBLIC_EXCHANGE,
            routing_key=topic,
            body=message,
            properties=pika.BasicProperties(
                delivery_mode=2
            )
        )

    def register_subscriber(self, subscriber: SubscriberInterface) -> None:
        if subscriber.topic() in self._subscribers:
            raise TopicSubscriberExistError(subscriber.topic())
        for i in range(subscriber.threads()):
            self._subscribers[subscriber.topic() + str(i)] = subscriber

    def _process_message(
            self,
            ch: BlockingChannel,
            method: spec.Basic.Deliver,
            _: spec.BasicProperties,
            body: bytes,
            subscriber: SubscriberInterface
    ) -> None:
        try:
            subscriber.callback(message=body.decode("utf-8"))
            ch.basic_ack(delivery_tag=method.delivery_tag)
        except Exception:
            ch.basic_nack(delivery_tag=method.delivery_tag)
            self.logger.exception(traceback.format_exc())

    def _start_consumers(self, queue_name: str) -> None:
        def on_message(
                ch: BlockingChannel,
                method: spec.Basic.Deliver,
                properties: spec.BasicProperties,
                body: bytes
        ) -> None:
            self._process_message(ch, method, properties, body, self._subscribers[queue_name])

        if queue_name not in self._subscribers_connections or self._subscribers_connections[queue_name].is_closed:
            self._subscribers_connections[queue_name] = self._create_connection()

        channel = self._subscribers_connections[queue_name].channel()
        channel.basic_qos(prefetch_count=1)

        channel.basic_consume(queue=self._subscribers[queue_name].topic(), on_message_callback=on_message)
        try:
            channel.start_consuming()
        except Exception:
            self.logger.exception(traceback.format_exc())

    def _create_and_start_consumer_thread(self, queue_name: str) -> Thread:
        thread = Thread(target=self._start_consumers, args=(queue_name,), daemon=True)
        thread.start()
        return thread

    def _start_monitor_thread(self) -> None:
        self._monitor_thread: Thread = Thread(target=self._monitor_threads, daemon=True)
        self._monitor_thread.start()

    def start_subscribing_threads(self) -> None:
        for queue_name, subscriber in self._subscribers.items():
            self._create_queue(queue=subscriber.topic())
            self._threads[queue_name] = self._create_and_start_consumer_thread(queue_name)

        self._start_monitor_thread()

        threading.Event().wait()

    def stop_subscribing_threads(self) -> None:
        for connection in self._subscribers_connections.values():
            connection.close()
        if self._connection and not self._connection.is_closed:
            self._connection.close()
