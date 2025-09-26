import yaml
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from exchange.explorer.basis.utils.permissions import get_all_permission_filenames

from ....utils.logging import get_logger


class Command(BaseCommand):
    def handle(self, *args, **kwargs):
        logger = get_logger()
        logger.info('Updating permissions...')
        for permissions_filename in get_all_permission_filenames():
            with open(permissions_filename) as permissions_file:
                data = yaml.safe_load(permissions_file)
                if not data:
                    continue
                for item in data:
                    codename = item.get('codename')
                    app_label = item.get('app_label')
                    model_name = item.get('model').lower()
                    content_type_query = {'model': model_name}
                    if app_label:
                        content_type_query['app_label'] = app_label
                    try:
                        permission = Permission.objects.get(codename=codename)

                    except Permission.DoesNotExist:
                        logger.info('Creating missing permission: {}'.format(codename))
                        Permission.objects.create(
                            name=item.get('name'),
                            codename=codename,
                            content_type=ContentType.objects.get(**content_type_query),
                        )
                        continue
                    except Permission.MultipleObjectsReturned:
                        logger.info('Ambiguous permission: {}!'.format(codename))
                        permissions = Permission.objects.filter(codename=codename)
                        for p in permissions:
                            logger.info(f'\t#{p.id} Model:{p.content_type.model}')
                        continue

                    if permission.name != item.get('name'):
                        logger.info('Updating permission name: {} => {}'.format(permission.name, item.get('name')))
                        permission.name = item.get('name')
                        permission.save(update_fields=['name'])
