from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend

from exchange.integrations.infobip import InfoBipService


class NobitexEmailBackend(EmailBackend):
    BACKEND = 'postfix'
    SENDER = 'Nobitex <info@nobitex.ir>'

    def __init__(self, **kwargs):
        if self.is_enabled():
            backend = settings.EMAIL_BACKEND_OPTIONS[self.BACKEND]
            kwargs['host'] = backend['host']
            kwargs['port'] = backend['port']
            kwargs['username'] = backend['user']
            kwargs['password'] = backend['password']
            kwargs['use_tls'] = backend.get('use_tls')
        super().__init__(**kwargs)

    def _send(self, email_message):
        email_message.from_email = self.SENDER
        super()._send(email_message)

    def is_enabled(self):
        return settings.IS_PROD or settings.IS_TESTNET


class NobitexEmailBackend2(NobitexEmailBackend):
    BACKEND = 'postfix2'


class NobitexEmailBackend3(NobitexEmailBackend):
    BACKEND = 'postfix3'


class NobitexEmailBackend4(NobitexEmailBackend):
    BACKEND = 'postfix4'


class InfoBipEmailBackend(NobitexEmailBackend):
    BACKEND = 'infobip'
    SENDER = 'no-reply@mail.nobitex.ir'

    def _send(self, email_message):
        message = email_message.message()
        InfoBipService.send(
            from_email=self.SENDER,
            subject=email_message.subject,
            text=email_message.alternatives[0][0],
            html=None,
            message_id=message['Message-ID'],
            recipient_emails=email_message.to,
            reply_to=[],
            cc=[],
            bcc=[],
        )
