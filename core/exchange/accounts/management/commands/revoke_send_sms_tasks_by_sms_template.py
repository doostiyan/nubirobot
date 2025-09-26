from django.core.management.base import BaseCommand

from exchange.accounts.functions import revoke_sms_tasks_by_template


class Command(BaseCommand):
    # Resources:
    # - https://docs.celeryq.dev/en/latest/userguide/workers.html#revoke-revoking-tasks
    # - https://stackoverflow.com/questions/39191238/revoke-a-task-from-celery

    help = (
        'Revoke celery tasks that send sms messages by template. '
        'Enter the comma-separated sms templates as argument to run the command, or use "all" to select all templates. '
        'e.g.: "python manage.py revoke_send_sms_tasks_by_sms_template result, templates"'
        'e.g.: "python manage.py revoke_send_sms_tasks_by_sms_template all"'
    )

    def add_arguments(self, parser):
        parser.add_argument('templates', type=str, help='Sms template not to be sent')

    def handle(self, *args, **kwargs):
        try:
            result, templates = revoke_sms_tasks_by_template(kwargs['templates'])
            self.stdout.write(
                self.style.SUCCESS('Revoking celery tasks scheduled to send any sms of below templates:\n')
            )
            self.stdout.write(self.style.SUCCESS(', '.join(template for template in templates)))
            self.stdout.write(self.style.SUCCESS('\nList of revoked sms messages:'))
            self.stdout.write(
                self.style.SUCCESS('\n'.join([f'(sms_id: {res[0]}, task_id: {res[1]})' for res in result]))
            )
        except Exception as e:
            self.stdout.write(self.style.ERROR(str(e)))
