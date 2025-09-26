from django.test import TransactionTestCase
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.models import Settings
from exchange.marketing.models import UTMParameter
from tests.base.utils import TransactionTestFastFlushMixin


class TestUTMParameterTests(TransactionTestFastFlushMixin, TransactionTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.user = User.objects.create(
            username='TestUTMParameterTests@nobitex.ir',
            email='TestUTMParameterTests@nobitex.ir',
            password='!',
            first_name='test',
            last_name='test',
            user_type=User.USER_TYPES.level0,
        )

    def get_user_utm(self):
        return UTMParameter.objects.filter(user=self.user).first()

    def test_direct_utm(self):
        assert not self.get_user_utm()
        UTMParameter.set_user_utm_parameters(self.user)
        utm: UTMParameter = self.get_user_utm()
        assert utm is None

    def test_utm_parameter_successful(self):
        assert not self.get_user_utm()
        UTMParameter.set_user_utm_parameters(
            self.user, 'the_source', 'the_medium', 'the_campaign', 'the_term', 'the_content', 'the_id'
        )

        utm: UTMParameter = self.get_user_utm()
        assert utm
        assert utm.source == 'the_source'
        assert utm.medium == 'the_medium'
        assert utm.campaign == 'the_campaign'
        assert utm.term == 'the_term'
        assert utm.content == 'the_content'
        assert utm.utm_id == 'the_id'

    def test_utm_set_some_of_parameters(self):
        assert not self.get_user_utm()
        UTMParameter.set_user_utm_parameters(self.user, 'the_source', 'the_medium')

        utm: UTMParameter = self.get_user_utm()
        assert utm
        assert utm.source == 'the_source'
        assert utm.medium == 'the_medium'
        assert not utm.campaign
        assert not utm.term
        assert not utm.content
        assert not utm.utm_id

    def test_utm_set_with_bad_value(self):
        assert not self.get_user_utm()
        UTMParameter.set_user_utm_parameters(self.user, 'the_source', 'the_medium', '👓', '🏀', 'drop users;')

        utm: UTMParameter = self.get_user_utm()
        assert utm
        assert utm.source == 'the_source'
        assert utm.medium == 'the_medium'
        assert not utm.campaign
        assert not utm.term
        assert not utm.content
        assert not utm.utm_id

    def test_utm_set_duplicate_for_user(self):
        assert not self.get_user_utm()
        UTMParameter.set_user_utm_parameters(self.user, 'the_source', 'the_medium')

        utm: UTMParameter = self.get_user_utm()
        assert utm
        assert utm.source == 'the_source'
        assert utm.medium == 'the_medium'

        UTMParameter.set_user_utm_parameters(self.user, 'the_source2', 'the_medium2')

        utm = self.get_user_utm()
        assert utm
        assert utm.source == 'the_source'
        assert utm.medium == 'the_medium'


class TestUTMRegisterAPITests(APITestCase):
    def setUp(self) -> None:
        Settings.set("email_register", 'yes')

    def get_user_utm(self):
        self.user = User.objects.get(username='test@nobitex.com')
        return UTMParameter.objects.filter(user=self.user).first()

    def register_user(self, **kwargs):
        data = {
            'email': 'test@nobitex.com',
            'username': 'test@nobitex.com',
            'password1': 'P@Sw0rd123456789',
            'password2': 'P@Sw0rd123456789',
        }
        data.update(kwargs)
        self.client.post(
            '/auth/registration/',
            data,
        )

    def test_direct_utm(self):
        assert not UTMParameter.objects.all()
        self.register_user()
        utm: UTMParameter = self.get_user_utm()
        assert utm is None

    def test_utm_parameter_successful(self):
        assert not UTMParameter.objects.all()
        self.register_user(
            **{
                'utmSource': 'the_source',
                'utmMedium': 'the_medium',
                'utmCampaign': 'the_campaign',
                'utmTerm': 'the_term',
                'utmContent': 'the_content',
                'utmId': 'the_id',
            }
        )

        utm: UTMParameter = self.get_user_utm()
        assert utm
        assert utm.source == 'the_source'
        assert utm.medium == 'the_medium'
        assert utm.campaign == 'the_campaign'
        assert utm.term == 'the_term'
        assert utm.content == 'the_content'
        assert utm.utm_id == 'the_id'

    def test_utm_set_some_of_parameters(self):
        assert not UTMParameter.objects.all()
        self.register_user(
            **{
                'utmSource': 'the_source',
                'utmMedium': 'the_medium',
            }
        )

        utm: UTMParameter = self.get_user_utm()
        assert utm
        assert utm.source == 'the_source'
        assert utm.medium == 'the_medium'
        assert not utm.campaign
        assert not utm.term
        assert not utm.content
        assert not utm.utm_id

    def test_utm_set_with_bad_value(self):
        assert not UTMParameter.objects.all()
        self.register_user(
            **{
                'utmSource': 'the_source',
                'utmMedium': 'the_medium',
                'utmCampaign': '👓',
                'utmTerm': '🏀',
                'utmContent': 'drop users;',
            }
        )

        utm: UTMParameter = self.get_user_utm()
        assert utm
        assert utm.source == 'the_source'
        assert utm.medium == 'the_medium'
        assert not utm.campaign
        assert not utm.term
        assert not utm.content
        assert not utm.utm_id

    def test_utm_set_special_character_value(self):
        assert not UTMParameter.objects.all()
        self.register_user(
            **{
                'utmSource': 'the_source',
                'utmMedium': 'the_medium',
                'utmCampaign': 'test-campaign',
                'utmTerm': 'test.com',
                'utmContent': 'test+test2',
            }
        )

        utm: UTMParameter = self.get_user_utm()
        assert utm
        assert utm.source == 'the_source'
        assert utm.medium == 'the_medium'
        assert utm.campaign == 'test-campaign'
        assert utm.term == 'test.com'
        assert utm.content == 'test+test2'
        assert not utm.utm_id

    def test_utm_set_value_with_over_255_character(self):
        assert not UTMParameter.objects.all()
        self.register_user(
            **{
                'utmSource': 'the_source',
                'utmMedium': 'the_medium',
                'utmCampaign': 'test-campaign',
                'utmTerm': 'testTerm.123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.'
                '123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.'
                '123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.'
                '123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.123-+',
                'utmContent': 'test+test2',
            }
        )
        utm: UTMParameter = self.get_user_utm()
        assert utm
        assert utm.source == 'the_source'
        assert utm.medium == 'the_medium'
        assert utm.campaign == 'test-campaign'
        assert utm.term == (
            'testTerm.123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.'
            '123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.'
            '123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.123-+testTerm.'
            '123-+tes'
        )
        assert utm.content == 'test+test2'
        assert not utm.utm_id
