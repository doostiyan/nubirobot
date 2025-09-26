import datetime

from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from ipware import get_client_ip
from rest_framework import status

from exchange.accounts.models import UserOTP
from exchange.base.api import APIView, api
from exchange.base.decorators import measure_api_execution
from exchange.base.parsers import parse_str
from exchange.blockchain.models import CurrenciesNetworkName
from exchange.security.models import AddressBook, AddressBookItem
from exchange.security.validations import check_enable_2fa, validate_address, validate_otp, validate_tag, validate_tfa


class ListCreateAddressBookView(APIView):
    @method_decorator(ratelimit(key='user_or_ip', rate='20/m', method='GET', block=True))
    @method_decorator(measure_api_execution(api_label='addressbookGetAddresses'))
    def get(self, request):
        """GET /address_book"""
        network = parse_str(self.g('network'))
        address_book = AddressBook.get(self.request.user)
        network = CurrenciesNetworkName.get_network_from_pseudo_network(network)
        if address_book:
            addresses = (
                AddressBookItem.available_objects.filter(address_book=address_book, network=network.upper())
                if network
                else AddressBookItem.available_objects.filter(address_book=address_book).all()
            )
        else:
            addresses = []
        return self.response({
            "status": "ok",
            "data": addresses,
        })

    @method_decorator(ratelimit(key='user_or_ip', rate='6/m', method='POST', block=True))
    @method_decorator(measure_api_execution(api_label='addressbookAddAddress'))
    def post(self, request):
        """POST /address_book"""
        user = request.user
        otp_code = parse_str(self.g('otpCode'), required=True)
        tfa_code = parse_str(self.g('tfaCode'), required=True)
        address = parse_str(self.g('address'), required=True)
        title = parse_str(self.g('title'), required=True)
        network = parse_str(self.g('network'), required=True).upper()
        tag = self.g('tag') or None

        check_enable_2fa(user)
        otp_obj = validate_otp(user, otp_code, UserOTP.OTP_Usage.address_book)
        validate_tfa(user, tfa_code)
        network = CurrenciesNetworkName.get_network_from_pseudo_network(network)
        validate_address(address, network)
        if tag:
            validate_tag(tag, network)

        if user.has_new_unknown_login(duration=datetime.timedelta(hours=1)):
            return JsonResponse(
                {
                    'status': 'failed',
                    'code': 'NewDeviceLoginRestriction',
                    'message': 'Adding address to address book is restricted for 1 hour after logging in from new device.',
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        ip = get_client_ip(request)
        ip = ip[0] if ip else None
        user_agent = (request.headers.get('user-agent') or 'unknown')[:255]
        address_book = AddressBook.add_address(user=user, title=title, address=address, user_agent=user_agent,
                                               network=network, ip=ip, tag=tag)
        otp_obj.mark_as_used()
        return self.response({
            "status": "ok",
            "data": address_book,
        })


class DeleteAddressBookView(APIView):

    @method_decorator(ratelimit(key='user_or_ip', rate='6/m', method='DELETE', block=True))
    @method_decorator(measure_api_execution(api_label='addressbookDeleteAddress'))
    def delete(self, request, pk):
        """DELETE /address_book/<int:pk>/delete"""
        try:
            AddressBook.delete_address(self.request.user, pk)
        except ObjectDoesNotExist:
            return JsonResponse({
                'status': 'failed',
                'code': "NotFound",
                'message': "address does not exist"
            }, status=status.HTTP_404_NOT_FOUND)

        return self.response({"status": "ok"})


@ratelimit(key='user_or_ip', rate='6/m', block=True)
@measure_api_execution(api_label='addressbookWhitelistOn')
@api
def activate_whitelist(request):
    AddressBook.activate_address_book(request.user)
    return {"status": "ok"}


@ratelimit(key='user_or_ip', rate='6/m', block=True)
@measure_api_execution(api_label='addressbookWhitelistOff')
@api
def deactivate_whitelist(request):
    otp_code = parse_str(request.g('otpCode'), required=True)
    tfa_code = parse_str(request.g('tfaCode'), required=True)
    user = request.user

    check_enable_2fa(user)
    otp_obj = validate_otp(user, otp_code, UserOTP.OTP_Usage.deactivate_whitelist)
    validate_tfa(user, tfa_code)

    AddressBook.deactivate_address_book(user)
    otp_obj.mark_as_used()
    return {"status": "ok"}
