from decimal import Decimal
from typing import List

from django.conf import settings
from django.http import JsonResponse
from rest_framework import status

from exchange.accounts.models import User
from exchange.base.calendar import ir_now
from exchange.base.models import Currencies, get_currency_codename
from exchange.socialtrade.models import Leader, LeadershipBlacklist, LeadershipRequest, SocialTradeAvatar
from tests.socialtrade.helpers import SocialTradeBaseAPITest


class LeadershipRequestAPITest(SocialTradeBaseAPITest):
    url = '/social-trade/leadership-requests'

    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)
        self.user.user_type = User.USER_TYPES.level2
        self.user.save()
        vp = self.user.get_verification_profile()
        vp.email_confirmed = True
        vp.save()
        self.user_2 = User.objects.get(pk=204)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')
        self.avatar = self.create_avatar()

    def test_invalid_user_token_for_post_api(self):
        self.client.credentials(HTTP_AUTHORIZATION='Token BAD_TOKEN')
        response = self.client.post(self.url, data=self._get_api_request_data())
        self._check_api_failure_response(expected_response={'detail': 'توکن غیر مجاز'}, api_response=response,
                                         response_status=status.HTTP_401_UNAUTHORIZED)

    def test_ability_to_request_for_leadership(self):
        self._set_user_level(User.USER_TYPES.verified)
        expected_failure_response = {
            'status': 'failed',
            'code': 'PendingLeadershipRequestExist',
            'message': 'A pending leadership request exists.',
        }
        # Shouldn't be able to make a new request because another not-rejected request exists
        request_data = self._get_api_request_data()
        self._create_leadership_request(leadership_requests=[{'status': LeadershipRequest.STATUS.new}])
        response = self.client.post(self.url, data=request_data)
        self._check_api_failure_response(expected_response=expected_failure_response, api_response=response)

        expected_failure_response = {
            'status': 'failed',
            'code': 'LeaderAlreadyExist',
            'message': 'Leader already exists.',
        }
        # Shouldn't be able to make a new request because an active leader exists
        LeadershipRequest.objects.filter(user=self.user).delete()
        leader = self.create_leader(user=self.user)
        response = self.client.post(self.url, data=request_data)
        self._check_api_failure_response(expected_response=expected_failure_response, api_response=response)

        expected_failure_response = {
            'status': 'failed',
            'code': 'PendingLeadershipRequestExist',
            'message': 'A pending leadership request exists.',
        }

        # Shouldn't be able to make a new request because there is a not-rejected request after leader deletion
        leader.deleted_at = ir_now()
        leader.save()
        self._create_leadership_request(leadership_requests=[{'status': LeadershipRequest.STATUS.accepted}])
        response = self.client.post(self.url, data=request_data)
        self._check_api_failure_response(expected_response=expected_failure_response, api_response=response)

        # Should be able to make a new request because no not-rejected requests exist after leader deletion
        LeadershipRequest.objects.filter(user=self.user).delete()
        self._create_leadership_request(leadership_requests=[{'status': LeadershipRequest.STATUS.rejected}])
        response = self.client.post(self.url, data=request_data)
        self._check_post_api_success_response(request_data, response, object_counts=2)

        # Should be able to make a new request because there is no leader object and previous requests were all rejected
        Leader.objects.filter(user=self.user).delete()
        LeadershipRequest.objects.filter(user=self.user, status=LeadershipRequest.STATUS.new).delete()
        response = self.client.post(self.url, data=request_data)
        self._check_post_api_success_response(request_data, response, object_counts=2)

    def test_request_with_zero_fee(self):
        self._set_user_level(User.USER_TYPES.verified)
        data = self._get_api_request_data(subscriptionFee=Decimal(0))
        response = self.client.post(self.url, data=data)
        self._check_post_api_success_response(data, response, object_counts=1)

    def test_user_eligibility_for_leadership(self):
        self._set_user_level(User.USER_TYPES.level1)

        expected_response = {
            'status': 'failed', 'code': 'IneligibleUser', 'message': 'User is ineligible due to unverified email'
                                                                     ' or level.'
        }
        # Should not be able to request when user's level is below 2
        response = self.client.post(self.url, data=self._get_api_request_data())
        self._check_api_failure_response(expected_response=expected_response, api_response=response)

        # Should not be able to request when user is a system account
        self._set_user_level(User.USER_TYPES.system)
        response = self.client.post(self.url, data=self._get_api_request_data())
        self._check_api_failure_response(expected_response=expected_response, api_response=response)

        # Should not be able to request when email is not verified
        self._set_user_level(User.USER_TYPES.verified)
        self._set_email_verification(False)
        response = self.client.post(self.url, data=self._get_api_request_data())
        self._check_api_failure_response(expected_response=expected_response, api_response=response)

        # Should be able to request when email is verified and level is 3 or above
        self._set_email_verification(True)
        data = self._get_api_request_data()
        response = self.client.post(self.url, data=data)
        self._check_post_api_success_response(request_data=data, api_response=response)

    def test_nickname_validity(self):
        max_length = settings.SOCIAL_TRADE['maxNicknameLength']
        min_length = settings.SOCIAL_TRADE['minNicknameLength']
        expected_response = {
            'status': 'failed',
            'code': 'InvalidNickname',
            'message': f'Nickname should contain at least {min_length} and at most '
                       f'{max_length} English letters and numbers.'
        }

        # Should not choose nicknames that are not using English or numeric characters
        self._set_user_level(User.USER_TYPES.verified)
        data = self._get_api_request_data(nickname='فارسی')
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(expected_response=expected_response, api_response=response)

        # Should not choose nicknames with whitespaces
        data = self._get_api_request_data(nickname='nickname with whitespace')
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(expected_response=expected_response, api_response=response)

        # Should not leave nickname field empty
        data = self._get_api_request_data(nickname='')
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(
            expected_response={'status': 'failed', 'code': 'ParseError', 'message': 'Missing string value'},
            api_response=response, response_status=status.HTTP_400_BAD_REQUEST
        )

        # Should not choose nicknames with special characters
        data = self._get_api_request_data(nickname='withSpecialChar!@$')
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(expected_response=expected_response, api_response=response)

        # Should not choose nicknames with more than 24 characters
        data = self._get_api_request_data(nickname='WeDoNotAcceptVeryLongNicknamesLikeThisOne')
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(expected_response=expected_response, api_response=response)

        # Should not choose nicknames with less than 4 characters
        data = self._get_api_request_data(nickname='A')
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(expected_response=expected_response, api_response=response)

    def test_nickname_uniqueness(self):
        expected_response = {
            'status': 'failed',
            'code': 'NicknameExists',
            'message': 'Nickname is already picked by another user.'
        }
        self._set_user_level(User.USER_TYPES.verified)

        # Should not be able to choose a nickname that another user has chosen
        self._create_leadership_request(
            leadership_requests=[{'user': self.user_2, 'status': LeadershipRequest.STATUS.new, 'nickname': 'Nickname1'}]
        )
        data = self._get_api_request_data(nickname='Nickname1')
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(expected_response=expected_response, api_response=response)

        # Should not be able to choose the same nickname as another chosen nickname but with lower or upper case letters
        data = self._get_api_request_data(nickname='nICKnAME1')
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(expected_response=expected_response, api_response=response)

        data = self._get_api_request_data(nickname='nICKnAME')
        response = self.client.post(self.url, data=data)
        self._check_post_api_success_response(request_data=data, api_response=response, object_counts=2)

        # Should be able to choose a nickname that another user previously chose but was rejected
        LeadershipRequest.objects.all().delete()
        self._create_leadership_request(
            leadership_requests=[{'user': self.user_2, 'status': LeadershipRequest.STATUS.rejected,
                                  'nickname': 'nickname1'}]
        )
        data = self._get_api_request_data(nickname='nickname1')
        response = self.client.post(self.url, data=data)
        self._check_post_api_success_response(request_data=data, api_response=response, object_counts=2)

        # Should be able to choose a nickname that the same user has chosen before
        LeadershipRequest.objects.all().delete()
        self._create_leadership_request(
            leadership_requests=[{'user': self.user, 'status': LeadershipRequest.STATUS.rejected,
                                  'nickname': 'nickname1'}]
        )
        data = self._get_api_request_data(nickname='nickname1')
        response = self.client.post(self.url, data=data)
        self._check_post_api_success_response(request_data=data, api_response=response, object_counts=2)

    def test_subscription_fee_currency_validation(self):
        expected_response = {
            'status': 'failed',
            'code': 'InvalidSubscriptionCurrency',
            'message': 'Cannot choose this currency as the subscription fee currency.'
        }

        # Should not choose currencies other than usdt and rls
        self._set_user_level(User.USER_TYPES.verified)
        data = self._get_api_request_data(subscriptionCurrency='btc')
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(expected_response=expected_response, api_response=response)

    def test_subscription_fee_when_it_is_very_high(self):
        expected_response = {
            'status': 'failed',
            'code': 'SubscriptionFeeIsHigh',
            'message': 'Subscription fee is very high.',
        }

        # Should not ask for more than 10 usdt as subscription fee
        self._set_user_level(User.USER_TYPES.verified)
        data = self._get_api_request_data(subscriptionFee=Decimal(10_000))
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(expected_response=expected_response, api_response=response)

        # Should not ask for more than 300_000_0 rls as subscription fee
        data = self._get_api_request_data(subscriptionFee=Decimal(10_000_000_0),
                                          subscriptionCurrency='rls')
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(expected_response=expected_response, api_response=response)

    def test_subscription_fee_precision(self):
        expected_response = {
            'status': 'failed',
            'code': 'ParseError',
            'message': 'numeric value should have precision of 1',
        }

        data = self._get_api_request_data(subscriptionFee=Decimal('1.1'), subscriptionCurrency='rls')
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(
            expected_response=expected_response,
            api_response=response,
            response_status=400,
        )

        expected_response = {
            'status': 'failed',
            'code': 'ParseError',
            'message': 'numeric value should have precision of 0.01',
        }

        data = self._get_api_request_data(subscriptionFee=Decimal('1.123'), subscriptionCurrency='usdt')
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(
            expected_response=expected_response,
            api_response=response,
            response_status=400,
        )

    def test_subscription_fee_when_it_is_very_low(self):
        expected_response = {
            'status': 'failed',
            'code': 'SubscriptionFeeIsLow',
            'message': 'Subscription fee is very low.',
        }

        # Should not ask for less than 2 usdt as subscription fee
        self._set_user_level(User.USER_TYPES.verified)
        data = self._get_api_request_data(subscriptionFee=Decimal(1))
        self.set_fee_boundary(Currencies.usdt, max_fee=Decimal(10), min_fee=Decimal(2))
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(expected_response=expected_response, api_response=response)

    def test_no_uploaded_file(self):
        expected_response = {'status': 'failed', 'code': 'NotFound', 'message': 'SocialTradeAvatar does not exist'}
        self._set_user_level(User.USER_TYPES.verified)
        data = self._get_api_request_data()
        SocialTradeAvatar.objects.filter(id=self.avatar.id).delete()
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(expected_response=expected_response, api_response=response,
                                         response_status=status.HTTP_404_NOT_FOUND)

    def test_get_leadership_request_when_no_request(self):
        response = self.client.get(self.url)
        self._check_get_api_success_response(response=response, leadership_requests=[])

    def test_getting_all_leadership_request(self):
        self._create_leadership_request(num_of_requests=2, leadership_requests=[{'status': 2}, {'status': 1}])
        requests = LeadershipRequest.objects.filter(user=self.user).order_by('-created_at')
        response = self.client.get(self.url)
        self._check_get_api_success_response(response=response, leadership_requests=requests)

    def test_not_getting_another_leaders_request(self):
        self._create_leadership_request(num_of_requests=3, leadership_requests=[{}, {}, {'user': self.user_2}])
        requests = LeadershipRequest.objects.filter(user=self.user).order_by('-created_at')
        response = self.client.get(self.url)
        self._check_get_api_success_response(response=response, leadership_requests=requests)

    def test_invalid_user_token_for_get_api(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token BAD_TOKEN')
        self._create_leadership_request(num_of_requests=3, leadership_requests=[{}, {}, {'user': self.user_2}])
        response = self.client.get(self.url)
        self._check_api_failure_response(expected_response={'detail': 'توکن غیر مجاز'}, api_response=response,
                                         response_status=status.HTTP_401_UNAUTHORIZED)

    def test_user_in_blacklist(self):
        expected_response = {'status': 'failed', 'code': 'UserBlacklisted', 'message': 'User is blacklisted.'}

        self._set_user_level(User.USER_TYPES.verified)
        # Block user
        blacklist = LeadershipBlacklist.objects.create(user=self.user)
        data = self._get_api_request_data()
        response = self.client.post(self.url, data=data)
        self._check_api_failure_response(expected_response=expected_response, api_response=response)

        blacklist.delete()
        response = self.client.post(self.url, data=data)
        self._check_post_api_success_response(request_data=data, api_response=response, object_counts=1)

    def _get_api_request_data(self, **kwargs):
        data = {
            'nickname': 'BestLeader',
            'avatarId': self.avatar.id,
            'subscriptionCurrency': 'usdt',
            'subscriptionFee': Decimal(10),
        }
        data.update(**kwargs)
        return data

    def _check_api_failure_response(self, expected_response: dict, api_response: JsonResponse,
                                    response_status=status.HTTP_422_UNPROCESSABLE_ENTITY):
        assert api_response.status_code == response_status
        response_json = api_response.json()
        for key in expected_response.keys():
            assert key in response_json
            assert response_json[key] == expected_response[key]

    def _check_post_api_success_response(self, request_data: dict, api_response: JsonResponse, object_counts: int = 1):
        assert api_response.status_code == status.HTTP_200_OK
        response_json = api_response.json()
        assert 'status' in response_json
        assert response_json['status'] == 'ok'
        assert 'data' in response_json
        assert LeadershipRequest.objects.count() == object_counts
        leadership_request = LeadershipRequest.objects.filter(user=self.user).order_by('-created_at').first()
        self._check_leadership_request_data(leadership_request, response_json['data'], request_data)

    def _check_leadership_request_data(
        self,
        leadership_request: LeadershipRequest,
        response_data: dict,
        request_data: dict,
    ):
        fields = [
            'id',
            'nickname',
            'avatar',
            'subscriptionFee',
            'subscriptionCurrency',
            'createdAt',
            'lastUpdate',
            'status',
            'reason',
        ]
        for field in fields:
            assert field in response_data
        assert response_data['id'] == leadership_request.id
        assert response_data['nickname'] == leadership_request.nickname == request_data['nickname']
        assert response_data['avatar'] == {
            'id': leadership_request.avatar.id,
            'image': leadership_request.avatar.image.url,
        }
        assert Decimal(response_data['subscriptionFee']) == leadership_request.subscription_fee
        assert Decimal(response_data['subscriptionFee']) == request_data['subscriptionFee']
        assert response_data['subscriptionCurrency'] == get_currency_codename(leadership_request.subscription_currency)
        assert response_data['subscriptionCurrency'] == request_data['subscriptionCurrency']
        assert response_data['createdAt'] == leadership_request.created_at.isoformat()
        assert response_data['lastUpdate'] == leadership_request.updated_at.isoformat()
        assert response_data['status'] == leadership_request.get_status_display()
        assert response_data['reason'] == leadership_request.reason

    def _create_leadership_request(self, num_of_requests: int = 1, leadership_requests=None):
        if leadership_requests is None:
            leadership_requests = []
        request_dicts = []
        for i in range(num_of_requests):
            request_dicts.append(
                {
                    'user': self.user,
                    'nickname': f'nickname{i}',
                    'avatar': self.avatar,
                    'subscription_fee': Decimal(5),
                    'subscription_currency': Currencies.usdt,
                    'status': LeadershipRequest.STATUS.rejected,
                    'reason': None,
                }
            )
            if leadership_requests and i < len(leadership_requests):
                request_dicts[i].update(leadership_requests[i])
        LeadershipRequest.objects.bulk_create(
            [LeadershipRequest(**request_dicts[i]) for i in range(len(request_dicts))]
        )

    def _set_user_level(self, level: int):
        self.user.user_type = level
        self.user.save()

    def _set_email_verification(self, confirmed: bool):
        vp = self.user.get_verification_profile()
        vp.email_confirmed = confirmed
        vp.save()

    def _check_get_api_success_response(self, response: JsonResponse,
                                        leadership_requests: List[LeadershipRequest]):
        assert response.status_code == status.HTTP_200_OK
        response_json = response.json()
        assert 'status' in response_json
        assert response_json['status'] == 'ok'
        assert 'data' in response_json
        assert len(leadership_requests) == len(response_json['data'])
        for i, leadership_request in enumerate(leadership_requests):
            response_data = response_json['data'][i]
            assert response_data['id'] == leadership_request.id
            assert response_data['nickname'] == leadership_request.nickname
            assert response_data['avatar'] == {
                'id': leadership_request.avatar.id,
                'image': leadership_request.avatar.image.url,
            }
            assert Decimal(response_data['subscriptionFee']) == leadership_request.subscription_fee
            assert response_data['subscriptionCurrency'] == \
                   get_currency_codename(leadership_request.subscription_currency)
            assert response_data['createdAt'] == leadership_request.created_at.isoformat()
            assert response_data['lastUpdate'] == leadership_request.updated_at.isoformat()
            assert response_data['status'] == leadership_request.get_status_display()
            assert response_data['reason'] == leadership_request.reason
