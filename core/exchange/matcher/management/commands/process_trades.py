"""Trade Processor Daemon"""
import signal
import time

from django.conf import settings
from django.core.management.base import BaseCommand

from exchange.accounts.models import Notification
from exchange.base.logging import report_exception
from exchange.matcher.tradeprocessor import TradeProcessor

# Exit Signal Handler
SHOULD_EXIT = False


def graceful_exit_handler(sig, frame):
    global SHOULD_EXIT  # noqa: PLW0603
    SHOULD_EXIT = True


class Command(BaseCommand):
    def register_signal_handler(self):
        signal.signal(signal.SIGHUP, graceful_exit_handler)

    def notify_admins(self, message, title=None):
        """Send a notification to admins group in Telegram."""
        if not settings.IS_PROD:
            return
        Notification.notify_admins(
            message,
            title=title or '🏁 TradeProcessor',
            channel='matcher',
        )

    def send_startup_notice(self):
        """Send start notifications."""
        self.notify_admins(f'Started on {settings.SERVER_NAME} {settings.RELEASE_VERSION}-{settings.CURRENT_COMMIT}')

    def handle(self, *args, **kwargs):
        self.register_signal_handler()
        self.send_startup_notice()

        try:
            while True:
                if SHOULD_EXIT:
                    print('Received SIGHUP')
                    break
                processor = TradeProcessor(commit_trade=False)
                try:
                    processor.do_round()
                    processor.bulk_update_trades()
                except Exception as e:  # noqa: BLE001
                    report_exception()
                    print(f'[Fatal] Exception: {e}')
                    self.notify_admins(f'Exception: {e}')
                    time.sleep(10)
                time.sleep(1 if processor.trades_count < 100 else 0.1)
        except KeyboardInterrupt:
            pass
        print('Done.')
