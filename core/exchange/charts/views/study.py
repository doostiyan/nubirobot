import json

from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django_ratelimit.decorators import ratelimit
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from exchange.charts import common
from exchange.charts.models import StudyTemplate


@ratelimit(key='user_or_ip', rate='30/1m', block=True)
@api_view(['POST', 'GET', 'DELETE', 'OPTIONS'])
@permission_classes([IsAuthenticated])
@csrf_exempt
def process_request(request):
    parsed_request = common.parse_request(request, allow_empty_user_id=True)

    if parsed_request['error'] is not None:
        return parsed_request['error']

    if parsed_request['response'] is not None:
        return parsed_request['response']

    client_id = parsed_request["clientId"]
    template_name = request.GET.get('template', '')

    if request.method == 'GET':
        if template_name == '':
            return get_all_templates_list(client_id, request.user.id)
        else:
            return get_template(client_id, request.user.id, template_name)

    elif request.method == 'DELETE':
        if template_name == '':
            return common.error('Wrong template id')
        else:
            return remove_template(client_id, request.user.id, template_name)

    elif request.method == 'POST':
        template_name = request.POST.get('name')
        content = request.POST.get('content')
        return create_or_update_template(client_id, request.user.id, template_name, content)

    else:
        return common.error('Wrong request')


def get_all_templates_list(client_id, user_id):
    items = (
        StudyTemplate.objects.using(settings.READ_DB).defer('content').filter(ownerSource=client_id, user_id=user_id)
    )
    result = map(lambda x: {'name': x.name}, items)
    return common.response(json.dumps({'status': "ok", 'data': list(result)}))


def get_template(client_id, user_id, name):
    try:
        item = StudyTemplate.objects.using(settings.READ_DB).get(ownerSource=client_id, user_id=user_id, name=name)
        result = json.dumps({'status': 'ok', 'data': {'name': item.name, 'content': item.content}})
        return common.response(result)
    except:
        return common.error('StudyTemplate not found')


def remove_template(client_id, user_id, name):
    try:
        item = StudyTemplate.objects.using(settings.READ_DB).get(ownerSource=client_id, user_id=user_id, name=name)
        item.delete(using=settings.WRITE_DB)
        return common.response(json.dumps({'status': 'ok'}))
    except:
        return common.error('StudyTemplate not found')


def create_or_update_template(client_id, user_id, name, content):
    new_item, created = StudyTemplate.objects.get_or_create(ownerSource=client_id, user_id=user_id, name=name)

    update_fields = ['content']

    if new_item.ownerId != str(user_id):
        new_item.ownerId = str(user_id)
        update_fields.append('ownerId')

    new_item.content = content
    new_item.save(update_fields=update_fields)

    return common.response(json.dumps({'status': 'ok'}))
