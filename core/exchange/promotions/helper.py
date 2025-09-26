
from uuid import UUID
from exchange.accounts.models import User
from exchange.promotions.exceptions import WebEngageUserIdDoesNotExist


def get_user_id_with_webengage_cuid(uuid: UUID):
    try:
        user = User.objects.get(webengage_cuid=uuid)
        return user.id
    except:
        raise WebEngageUserIdDoesNotExist()
