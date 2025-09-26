from exchange.base.api import APIView, is_internal_ip, SemanticAPIError
from exchange.base.parsers import parse_utc_timestamp_to_ir_time, parse_int
from exchange.features.utils import is_feature_enabled
from exchange.system.models import BotTransaction


class ListBotTransactionView(APIView):
    def get(self, request):
        ip = request.META['REMOTE_ADDR']
        if not is_internal_ip(ip) or not is_feature_enabled(user=request.user, feature='bot_transactions'):
            raise SemanticAPIError(message='AccessDenied', description='Access Denied!')
        ir_time = self.g('since', '')
        ir_time = parse_utc_timestamp_to_ir_time(ir_time) if ir_time else None
        transaction_id = parse_int(self.g('transactionId', '0'))

        transactions = BotTransaction.get_transactions(ir_time, transaction_id, request.user)

        return self.response({
            'status': 'ok',
            'data': {'transactions': transactions},
        })
