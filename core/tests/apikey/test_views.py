import datetime

from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework.status import HTTP_400_BAD_REQUEST, HTTP_404_NOT_FOUND
from rest_framework.test import APIClient, APITestCase

from exchange.accounts.models import User
from exchange.apikey.models import Key, Permission


class TestKeyAPIs2FA(APITestCase):
    def test_request_without_2fa(self) -> None:
        user = User.objects.get(pk=201)

        user.requires_2fa = True
        user.save(update_fields=['requires_2fa'])

        client = APIClient(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user201token',
        )

        response = client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        )

        assert response.status_code == HTTP_400_BAD_REQUEST  # type: ignore[attr-defined]

        data = response.json()  # type: ignore[attr-defined]

        assert data['status'] == 'failed', response
        assert data['code'] == 'Missing2FA', response
        assert data['message'] == '2FA is required', response

    def test_request_invalid_2fa(self) -> None:
        user = User.objects.get(pk=201)

        user.requires_2fa = True
        user.save(update_fields=['requires_2fa'])

        client = APIClient(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user201token',
            HTTP_X_TOTP='123456',
        )

        response = client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        )

        assert response.status_code == HTTP_400_BAD_REQUEST  # type: ignore[attr-defined]

        data = response.json()  # type: ignore[attr-defined]

        assert data['status'] == 'failed', response
        assert data['code'] == 'Invalid2FA', response
        assert data['message'] == '2FA is invalid', response

    def test_request_user_without_2fa(self) -> None:
        client = APIClient(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user201token',
            HTTP_X_TOTP='123456',
        )

        response = client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        )

        assert response.status_code == HTTP_400_BAD_REQUEST  # type: ignore[attr-defined]

        data = response.json()  # type: ignore[attr-defined]

        assert data['status'] == 'failed', response
        assert data['code'] == 'UserWithout2FA', response
        assert data['message'] == 'Use 2FA shoud be enabled', response


class APIKeyTestCase(APITestCase):
    def refresh_otp(self) -> None:
        """
        refresh otp will allow you to use same otp for multiple
        requests in a single test.
        """

        self.device.refresh_from_db()
        self.device.last_t = -1
        self.device.save()

    def setUp(self) -> None:
        self.user = User.objects.get(pk=201)

        self.user.requires_2fa = True

        # Create a TOTPDevice for the user
        self.device = TOTPDevice.objects.create(
            user=self.user,
            name='test-device',
            confirmed=True,  # Set to True to allow OTP verification
        )

        self.user.save(update_fields=['requires_2fa'])

        # Generate a valid OTP token for the current time using django_otp.oath.totp
        # The totp function expects the key, time step (default 30s), and digits (default 6)
        totp_token = totp(
            key=self.device.bin_key,
            step=self.device.step,  # Default is 30 seconds
            digits=self.device.digits,  # Default is 6 digits
        )

        # Convert the token to a string with leading zeros if needed
        otp_token = f'{totp_token:06d}'  # Ensure 6-digit format

        self.client = APIClient(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user201token',
            HTTP_X_TOTP=otp_token,
        )


class TestKeyAPIsCreation(APIKeyTestCase):
    def test_api_creation_with_invalid_permission(self):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'INVALID',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        ).json()

        assert response['status'] == 'failed', response
        assert response['code'] == 'ParseError', response
        assert response['message'] == ('permissions: Value error, permissions are not parsable')

    def test_api_creation_with_invalid_ip(self):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
                'ipAddressesWhitelist': ['188.121.146.46.'],
            },
            format='json',
        ).json()

        assert response['status'] == 'failed', response
        assert response['code'] == 'ParseError', response
        assert response['message'] == ('ipAddressesWhitelist: value is not a valid IPv4 or IPv6 address')

    def test_api_creation_without_description(self):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'permissions': 'READ,TRADE',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response
        assert response['key']['permissions'] == 'READ,TRADE'
        assert response['key']['ipAddressesWhitelist'] == ['188.121.146.46']

        keys = Key.objects.filter(owner=self.user).all()
        assert len(keys) == 1
        assert keys[0].name == 'testkey'
        assert keys[0].description == ''
        assert keys[0].ip_addresses_whitelist == ['188.121.146.46']
        assert Permission.READ in keys[0].permissions
        assert Permission.TRADE in keys[0].permissions
        assert Permission.WITHDRAW not in keys[0].permissions

    def test_api_creation_with_long_description(self):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing' * 1000,
                'permissions': 'READ,TRADE',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        ).json()

        assert response['status'] == 'failed', response
        assert response['code'] == 'ParseError', response
        assert response['message'] == 'description: String should have at most 1000 characters'

    def test_api_creation_without_name(self):
        response = self.client.post(
            '/apikeys/create',
            data={
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        ).json()

        assert response['status'] == 'failed', response
        assert response['code'] == 'ParseError', response
        assert response['message'] == ('name: Field required')

    def test_api_creation_with_ip(self):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE,WITHDRAW',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response
        assert response['key']['permissions'] == 'READ,TRADE,WITHDRAW'
        assert response['key']['ipAddressesWhitelist'] == ['188.121.146.46']

        keys = Key.objects.filter(owner=self.user).all()
        assert len(keys) == 1
        assert keys[0].name == 'testkey'
        assert keys[0].description == 'a just for testing'
        assert keys[0].ip_addresses_whitelist == ['188.121.146.46']
        assert Permission.READ in keys[0].permissions
        assert Permission.TRADE in keys[0].permissions
        assert Permission.WITHDRAW in keys[0].permissions

    def test_api_creation_with_expiration(self):
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE,WITHDRAW',
                'expirationDate': now.isoformat(),
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response
        assert response['key']['permissions'] == 'READ,TRADE,WITHDRAW'
        assert response['key']['expirationDate'] == now.isoformat('T').replace('+00:00', 'Z')

        keys = Key.objects.filter(owner=self.user).all()
        assert len(keys) == 1
        assert keys[0].name == 'testkey'
        assert keys[0].description == 'a just for testing'
        assert keys[0].expiration_date == now
        assert Permission.READ in keys[0].permissions
        assert Permission.TRADE in keys[0].permissions
        assert Permission.WITHDRAW in keys[0].permissions

    def test_api_creation_with_expiration_and_ip(self):
        now = datetime.datetime.now(tz=datetime.timezone.utc)

        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE,WITHDRAW',
                'ipAddressesWhitelist': ['188.121.146.46'],
                'expirationDate': now.isoformat(),
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response
        assert response['key']['permissions'] == 'READ,TRADE,WITHDRAW'
        assert response['key']['ipAddressesWhitelist'] == ['188.121.146.46']
        assert response['key']['expirationDate'] == now.isoformat('T').replace('+00:00', 'Z')

        keys = Key.objects.filter(owner=self.user).all()
        assert len(keys) == 1
        assert keys[0].name == 'testkey'
        assert keys[0].description == 'a just for testing'
        assert keys[0].ip_addresses_whitelist == ['188.121.146.46']
        assert keys[0].expiration_date == now
        assert Permission.READ in keys[0].permissions
        assert Permission.TRADE in keys[0].permissions
        assert Permission.WITHDRAW in keys[0].permissions

    def test_api_creation_with_permissions_1(self):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'TRADE',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response
        assert response['key']['permissions'] == 'TRADE'
        assert response['key']['ipAddressesWhitelist'] == ['188.121.146.46']

        keys = Key.objects.filter(owner=self.user).all()
        assert len(keys) == 1
        assert keys[0].name == 'testkey'
        assert keys[0].description == 'a just for testing'
        assert keys[0].ip_addresses_whitelist == ['188.121.146.46']
        assert Permission.READ not in keys[0].permissions
        assert Permission.TRADE in keys[0].permissions
        assert Permission.WITHDRAW not in keys[0].permissions

    def test_api_creation_with_permissions_2(self):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'TRADE,READ',
                'ipAddressesWhitelist': ['188.121.146.46'],
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response
        assert response['key']['permissions'] == 'READ,TRADE'
        assert response['key']['ipAddressesWhitelist'] == ['188.121.146.46']

        keys = Key.objects.filter(owner=self.user).all()
        assert len(keys) == 1
        assert keys[0].name == 'testkey'
        assert keys[0].description == 'a just for testing'
        assert keys[0].ip_addresses_whitelist == ['188.121.146.46']
        assert Permission.READ in keys[0].permissions
        assert Permission.TRADE in keys[0].permissions
        assert Permission.WITHDRAW not in keys[0].permissions

    def test_api_creation_with_many_keys(self):
        for i in range(Key.MAX_KEYS_PER_USER):
            response = self.client.post(
                '/apikeys/create',
                data={
                    'name': f'testkey {i}',
                    'description': 'a just for testing',
                    'permissions': 'READ,TRADE',
                },
                format='json',
            ).json()

            assert response['status'] == 'ok', response
            self.refresh_otp()

        response = self.client.post(
            '/apikeys/create',
            data={
                'name': f'testkey {Key.MAX_IPS_PER_KEY}',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
            },
            format='json',
        ).json()

        assert response['status'] == 'failed', response
        assert response['code'] == 'ValidationError'
        assert response['message'] == 'users can only have 20 keys'


class TestKeyAPIsList(APIKeyTestCase):
    def test_api_list(self):
        for i in range(10):
            response = self.client.post(
                '/apikeys/create',
                data={
                    'name': f'testkey {i}',
                    'description': 'a just for testing',
                    'permissions': 'READ,TRADE',
                },
                format='json',
            ).json()

            assert response['status'] == 'ok', response
            self.refresh_otp()

        response = self.client.get(
            '/apikeys/list',
        ).json()

        assert response['status'] == 'ok', response
        keys = response['keys']
        assert len(keys) == 10

        for key in keys:
            assert 'name' in key
            assert 'description' in key
            assert key['description'] == 'a just for testing'
            assert 'permission_bits' not in key
            assert 'permissions' in key
            assert key['permissions'] == 'READ,TRADE'

    def test_api_list_with_two_users(self):
        user = User.objects.get(pk=202)

        user.requires_2fa = True

        device = TOTPDevice.objects.create(
            user=user,
            name='test-device',
            confirmed=True,
        )

        user.save()

        totp_token = totp(
            key=device.bin_key,
            step=device.step,
            digits=self.device.digits,
        )

        otp_token = f'{totp_token:06d}'

        client = APIClient(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user202token',
            HTTP_X_TOTP=otp_token,
        )

        for i in range(10):
            response = client.post(
                '/apikeys/create',
                data={
                    'name': f'testkey {i}',
                    'description': 'a just for testing',
                    'permissions': 'READ,TRADE',
                },
                format='json',
            )

            assert response.json()['status'] == 'ok', response  # type: ignore[attr-defined]
            device.last_t = 0
            device.save()

        for i in range(10):
            response = self.client.post(
                '/apikeys/create',
                data={
                    'name': f'testkey {i}',
                    'description': 'a just for testing',
                    'permissions': 'READ,TRADE',
                },
                format='json',
            ).json()

            assert response['status'] == 'ok', response
            self.refresh_otp()

        response = self.client.get(
            '/apikeys/list',
        ).json()

        assert response['status'] == 'ok', response
        keys = response['keys']
        assert len(keys) == 10

        for key in keys:
            assert 'name' in key
            assert 'description' in key
            assert key['description'] == 'a just for testing'
            assert 'permission_bits' not in key
            assert 'permissions' in key
            assert key['permissions'] == 'READ,TRADE'


class TestKeyAPIsDelete(APIKeyTestCase):
    def test_api_delete(self):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
            },
            format='json',
        ).json()
        self.refresh_otp()

        assert response['status'] == 'ok', response

        key = response['key']['key']

        response = self.client.post(
            f'/apikeys/delete/{key}',
        ).json()

        assert response['status'] == 'ok', response

        assert len(Key.objects.filter(owner=self.user)) == 0

    def test_api_delete_someone_else_key(self):
        user = User.objects.get(pk=202)

        user.requires_2fa = True

        device = TOTPDevice.objects.create(
            user=user,
            name='test-device',
            confirmed=True,
        )

        user.save()

        totp_token = totp(
            key=device.bin_key,
            step=device.step,
            digits=self.device.digits,
        )

        otp_token = f'{totp_token:06d}'

        client = APIClient(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user202token',
            HTTP_X_TOTP=otp_token,
        )

        response = client.post(
            '/apikeys/create',
            data={
                'name': 'testkey for user 202',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
            },
            format='json',
        ).json()  # type: ignore[attr-defined]

        assert response['status'] == 'ok', response
        device.last_t = 0
        device.save()

        key = response['key']['key']

        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey for user 201',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response
        self.refresh_otp()

        response = self.client.post(
            f'/apikeys/delete/{key}',
        )

        assert response.status_code == HTTP_404_NOT_FOUND


class TestKeyAPIsUpdate(APIKeyTestCase):
    def test_api_update(self):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response
        self.refresh_otp()

        key = response['key']['key']
        updated_at = response['key']['updatedAt']
        created_at = response['key']['createdAt']

        response = self.client.post(
            f'/apikeys/update/{key}',
            data={
                'ipAddressesWhitelist': ['188.121.146.46', '188.121.146.45'],
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response
        assert response['key']['ipAddressesWhitelist'] == ['188.121.146.46', '188.121.146.45']
        assert response['key']['updatedAt'] != updated_at
        assert response['key']['createdAt'] == created_at

    def test_api_update_bad_request(self):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
            },
            format='json',
        ).json()
        self.refresh_otp()

        assert response['status'] == 'ok', response

        key = response['key']['key']

        response = self.client.post(
            f'/apikeys/update/{key}',
            data={
                'ipAddressesWhitelist': '188.121.146.46',
            },
            format='json',
        ).json()

        assert response['status'] == 'failed', response
        assert response['code'] == 'ParseError', response
        assert response['message'] == ('ipAddressesWhitelist: Input should be a valid list')

    def test_api_update_not_found(self):
        response = self.client.post(
            '/apikeys/update/not-found',
            data={
                'ipAddressesWhitelist': ['188.121.146.46', '188.121.146.45'],
            },
            format='json',
        )

        assert response.status_code == HTTP_404_NOT_FOUND, response

    def test_api_update_with_invalid_ip(self):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response
        self.refresh_otp()

        key = response['key']['key']

        response = self.client.post(
            f'/apikeys/update/{key}',
            data={
                'ipAddressesWhitelist': ['188.121.146'],
            },
            format='json',
        ).json()

        assert response['status'] == 'failed', response
        assert response['code'] == 'ParseError', response
        assert response['message'] == ('ipAddressesWhitelist: value is not a valid IPv4 or IPv6 address')

    def test_api_update_with_many_ip(self):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response
        self.refresh_otp()

        key = response['key']['key']

        response = self.client.post(
            f'/apikeys/update/{key}',
            data={
                'ipAddressesWhitelist': ['188.121.146.45'] * (Key.MAX_IPS_PER_KEY + 1),
            },
            format='json',
        ).json()

        assert response['status'] == 'failed', response
        assert response['code'] == 'ValidationError', response
        assert response['message'] == 'each key can have at most 10 ip whitelist', response

    def test_api_update_invalid_field(self):
        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response
        self.refresh_otp()

        key = response['key']['key']
        updated_at = response['key']['updatedAt']

        response = self.client.post(
            f'/apikeys/update/{key}',
            data={
                'permissions': 'READ',
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response
        assert response['key']['permissions'] == 'READ,TRADE'
        assert response['key']['updatedAt'] == updated_at

    def test_api_update_someone_else_key(self):
        user = User.objects.get(pk=202)

        user.requires_2fa = True

        device = TOTPDevice.objects.create(
            user=user,
            name='test-device',
            confirmed=True,
        )

        user.save()

        totp_token = totp(
            key=device.bin_key,
            step=device.step,
            digits=self.device.digits,
        )

        otp_token = f'{totp_token:06d}'

        client = APIClient(
            HTTP_USER_AGENT='Mozilla/5.0',
            HTTP_AUTHORIZATION='Token user202token',
            HTTP_X_TOTP=otp_token,
        )

        response = client.post(
            '/apikeys/create',
            data={
                'name': 'testkey for user 202',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
            },
            format='json',
        ).json()  # type: ignore[attr-defined]

        assert response['status'] == 'ok', response

        key = response['key']['key']

        response = self.client.post(
            '/apikeys/create',
            data={
                'name': 'testkey for user 201',
                'description': 'a just for testing',
                'permissions': 'READ,TRADE',
            },
            format='json',
        ).json()

        assert response['status'] == 'ok', response
        self.refresh_otp()

        response = self.client.post(
            f'/apikeys/update/{key}',
            data={},
            format='json',
        )

        assert response.status_code == HTTP_404_NOT_FOUND
