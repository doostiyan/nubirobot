import json
from pathlib import Path

from django.core.management import BaseCommand
from django.template import Context, Template
from post_office.models import EmailTemplate

from exchange.notification.email.email_manager import EmailManager


class Command(BaseCommand):
    # TODO Change the command name (remove 'new') after full launch
    help = 'Debug email templates. Renders and saves an email template.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--template', type=str, help='Template Debug Case', nargs='?', default='set_anti_phishing_code'
        )
        parser.add_argument(
            '--data', type=str, help='Data Debug Case', nargs='?', default={'anti_phishing_code': 'jgghfhfhfd'}
        )

    def handle(self, *args, **kwargs):
        template = kwargs.get('template')
        data = json.loads(kwargs.get('data'))
        anti_phishing_code = data.get('anti_phishing_code')

        email_template = EmailTemplate.objects.get(name=template)
        data = EmailManager.prepare_email_data(data=data, email='example@example.com')
        if anti_phishing_code:
            data['anti_phishing_code'] = anti_phishing_code

        html_string = Template(email_template.html_content).render(Context(data))
        Path("debug_templates").mkdir(exist_ok=True)
        with open(f'debug_templates/{template}.html', 'w+') as f:
            f.write(html_string)
