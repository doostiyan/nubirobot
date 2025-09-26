from exchange.corporate_banking.managers import BulkCobankManager
from exchange.corporate_banking.models import COBANK_PROVIDER
from exchange.integrations.models import APICallLog


class ThirdpartyLog(APICallLog):
    COBANK_TO_THIRDPARTY_PROVIDER = {
        COBANK_PROVIDER.toman: APICallLog.PROVIDER.toman,
        COBANK_PROVIDER.jibit: APICallLog.PROVIDER.jibit,
    }

    objects = BulkCobankManager()

    class Meta:
        proxy = True
