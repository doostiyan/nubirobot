from django.apps import AppConfig


class CaptchaConfig(AppConfig):
    name = 'exchange.captcha'
    verbose_name = 'کپچت'

    def ready(self):
        pass
