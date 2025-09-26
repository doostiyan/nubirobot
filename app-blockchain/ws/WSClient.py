import json
import logging
import signal
import threading
import time
import traceback
from itertools import cycle
from threading import current_thread

import websocket
from django.core.cache import cache
from events import Events

# from exchange.base.logging import report_exception

# This restores the default Ctrl+C signal handler, which just kills the process
signal.signal(signal.SIGINT, signal.SIG_DFL)

log = logging.getLogger(__name__)

logging.basicConfig(level=logging.INFO)


class NumRetriesReached(Exception):
    pass


class WSClient(Events):
    """
    Create a websocket connection and request push notifications.
    :param Union[str, cycle, list] urls: Either a single Websocket URL, or a list of URLs
    :param list addresses: list of addresses you'd like to be notified when changing
    :param int keep_alive: seconds between a ping to the backend (defaults to 25seconds)
    After instanciating this class, you can add event slots for:
    * ``on_address``
    which will be called accordingly with the notification
    message received from the node:
    .. code-block:: python
        ws = WSClient(
            "wss://blockbook-ethereum.tronwallet.me/websocket",
            addresses=["0xba98d6a5ac827632e3457de7512d211e4ff7e8bd","0x73d0385f4d8e00c5e6504c6030f47bf6212736a8"]
        )
        ws.run_forever()
    """

    __events__ = ['on_blocks', 'on_addresses']
    required_ping = True

    def __init__(
        self,
        urls,
        *args,
        on_blocks=None,
        on_addresses=None,
        addresses=None,
        keep_alive=25,
        num_retries=-1,
        reset_cache_key=None,
        header=None,
        **kwargs
    ):

        self.num_retries = num_retries
        self.keepalive = None
        self._request_id = 0
        self.ws = None
        self.keep_alive = keep_alive
        self.run_event = threading.Event()
        self.addresses = addresses or []
        self.reset_cache_key = reset_cache_key
        self.header = header
        if isinstance(urls, cycle):
            self.urls = urls
        elif isinstance(urls, list):
            self.urls = cycle(urls)
        else:
            self.urls = cycle([urls])

        self.url = None

        # Instanciate Events
        Events.__init__(self)
        self.events = Events()

        # Store the objects we are interested in
        if on_blocks:
            self.on_blocks += on_blocks
        if on_addresses:
            self.on_addresses += on_addresses

    @property
    def subscribe_message(self):
        return {'id': 'subscribe_block', 'method': 'subscribeNewBlock', 'params': {}}

    @property
    def unsubscribe_message(self):
        return {'id': '', 'method': 'unsubscribeNewBlock', 'params': {}}

    @property
    def ping_message(self):
        return {'id': self.get_request_id(), 'method': 'ping', 'params': {}}

    def cancel_subscriptions(self):
        data = self.unsubscribe_message
        if data is not None:
            self.ws.send(json.dumps(data))

    def on_open(self, _, *args, **kwargs):
        """
        This method will be called once the websocket connection is established. It
        will.
        * login,
        * register to the database api, and
        * subscribe to the objects defined if there is a
          callback/slot available for callbacks
        """
        log.info('[Websocket] Open websocket connection')
        self.__set_subscriptions()
        if self.required_ping:
            self.keepalive = threading.Thread(target=self._ping)
            self.keepalive.setDaemon(True)
            self.keepalive.start()

    def reset_subscription(self):
        self.__set_subscriptions()

    def __set_subscriptions(self):
        # self.cancel_subscriptions()
        # Subscribe to events on the Backend and give them a
        # callback number that allows us to identify the event
        self._request_id = 0
        if self.on_blocks:
            log.debug('Subscribing to blocks')
            self.subscribe_blocks()
        else:
            log.debug('Subscribing to Addresses')
            self.subscribe_blocks()

    def subscribe_blocks(self):
        data = self.subscribe_message
        print(json.dumps(data))
        self.ws.send(json.dumps(data))

    def _ping(self):
        # We keep the connection alive by requesting a short object
        while not self.run_event.wait(self.keep_alive):
            if self.reset_cache_key is not None and cache.get(self.reset_cache_key, False):
                self.close()
                return
            log.info('Sending ping')
            data = self.ping_message
            self.ws.send(json.dumps(data))

    def on_message(self, _, reply, *args, **kwargs):
        """
        This method is called by the websocket connection on every message that is
        received.
        If we receive a ``notice``, we hand over post-processing and signalling of
        events to ``process_notice``.
        """
        log.debug(f'Received message: {str(reply)}')
        try:
            data = json.loads(reply, strict=False)
        except ValueError as error:
            log.critical(f'{str(error)}\n\n{traceback.format_exc()}')
            # report_exception()
            return
        reply_id = data.get('id')
        if reply_id != 'subscribe_block':
            return
        self.on_blocks(data)

    def on_error(self, _, error, *args, **kwargs):
        """Called on websocket errors."""
        log.exception(error)

    def on_close(self, _, *args, **kwargs):
        """Called when websocket connection is closed."""
        log.info(f'Closing WebSocket connection with {self.url}')
        self.close()

    def run_forever(self, *args, **kwargs):
        """
        This method is used to run the websocket app continuously.
        It will execute callbacks as defined and try to stay connected with the provided
        APIs
        """
        cnt = 0
        while not self.run_event.is_set():
            cnt += 1
            self.url = next(self.urls)
            log.debug(f'Trying to connect to node {self.url}')
            try:
                # websocket.enableTrace(True)
                websocket.setdefaulttimeout(50)
                self.ws = websocket.WebSocketApp(
                    self.url,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                    on_open=self.on_open,
                    header=self.header,
                )
                self.ws.run_forever(*args, **kwargs)
            except (websocket.WebSocketException, websocket.WebSocketProtocolException) as error:
                log.critical(f'{str(error)}\n\n{traceback.format_exc()}')

            except KeyboardInterrupt:
                self.ws.keep_running = False
                return

            except Exception as error:
                log.critical(f'{str(error)}\n\n{traceback.format_exc()}')

            finally:
                if 0 <= self.num_retries < cnt:
                    raise NumRetriesReached()

                sleeptime = (cnt - 1) * 2 if cnt < 10 else 10
                if sleeptime:
                    log.warning(
                        f'Lost connection to node during wsconnect(): {self.url} ({cnt}/{self.num_retries}) Retrying in {sleeptime} seconds'
                    )
                    time.sleep(sleeptime)

    def close(self, *args, **kwargs):
        """Closes the websocket connection and waits for the ping thread to close."""
        log.info('[Websocket] closing websocket')
        self.run_event.set()
        self.ws.close()

        if self.keepalive and self.keepalive.is_alive() and self.keepalive is not current_thread():
            self.keepalive.join()

        log.info('[Websocket] websocket closed')

    def get_request_id(self):
        self._request_id = (self._request_id + 1) % 1000
        return str(self._request_id)


class GethWSClient(WSClient):
    required_ping = False
    subscribe_id = None

    @property
    def subscribe_message(self):
        return {"jsonrpc": "2.0", "id": "subscribe_block", "method": "eth_subscribe", "params": ["newHeads"]}

    @property
    def unsubscribe_message(self):
        if self.subscribe_message is None:
            return None
        return {"jsonrpc": "2.0", "id": "subscribe_block", "method": "eth_unsubscribe",
                "params": [f"{self.subscribe_id}"]}

    def on_message(self, _, reply, *args, **kwargs):
        log.debug(f'Received message: {str(reply)}')
        try:
            data = json.loads(reply, strict=False)
        except ValueError as error:
            log.critical(f'{str(error)}\n\n{traceback.format_exc()}')
            # report_exception()
            return
        reply_id = data.get('id')
        if reply_id == 'subscribe_block':
            self.subscribe_id = data.get('result')
            return
        if data.get('method') != 'eth_subscription':
            return
        self.on_blocks(data)


class NearWSClient(WSClient):
    required_ping = False
    subscribe_id = None

    @property
    def subscribe_message(self):
        return {'jsonrpc': '2.0', 'id': 5, 'method': 'subscription', 'params': {'path': 'subscriptions.latestBlock'}}

    def on_message(self, _, reply, *args, **kwargs):
        log.debug(f'Received message: {str(reply)}')
        try:
            data = json.loads(reply, strict=False)
        except ValueError as error:
            log.critical(f'{str(error)}\n\n{traceback.format_exc()}')
            # report_exception()
            return
        reply_id = data.get('id')
        if reply_id != 5:
            return
        print(data)
        if reply_id == 5 and data.get('result').get('type') == 'started':
            return
        self.on_blocks(data)


class AvaxWSClient(WSClient):
    required_ping = True

    @property
    def subscribe_message(self):
        return {"event": "gs"}

    @property
    def ping_message(self):
        return {"event": "ping"}

    def on_message(self, _, reply, *args, **kwargs):
        log.debug(f'Received message: {str(reply)}')
        try:
            data = json.loads(reply, strict=False)
        except ValueError as error:
            log.critical(f'{str(error)}\n\n{traceback.format_exc()}')
            # report_exception()
            return
        if data.get('event'):
            return
        self.on_blocks(data)
