from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.marketing.models import SuggestionCategory, Suggestion


class SuggestionTests(APITestCase):
    fixtures = ['system', 'test_data']

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        cls.suggestion_category = SuggestionCategory.objects.create(title='test')
        cls.url = '/marketing/suggestion/add'
        cls.staff_user = User.objects.create_superuser(username='admin', email='admin@example.com', password='test')
        cls.valid_description = 'This is test'
        cls.not_valid_description = 'AB'

    def test_user_add_suggestion(self):
        self.client.force_login(self.staff_user)
        data = {
            'suggestionCategory': self.suggestion_category.id,
            'description': self.valid_description,
        }
        response = self.client.post(self.url, data=data).json()
        suggestion = Suggestion.objects.filter(
            category=self.suggestion_category,
            description=self.valid_description
        ).first()
        assert suggestion
        assert suggestion.allocated_by == self.staff_user
        self.assertDictEqual(response, {
            'status': 'ok',
            'suggestion': {
                "id": suggestion.id,
                "priority": "یک",
                "title": "test",
                "description": self.valid_description,
                "name": str(self.staff_user),
                "mobile": self.staff_user.mobile,
                "email": self.staff_user.email,
            },
        })

    def test_anonymous_user_add_suggestion(self):
        data = {
            'suggestionCategory': self.suggestion_category.id,
            'description': self.valid_description,
            'email': 'test@gmail.com',
        }
        response = self.client.post(
            REMOTE_ADDR="127.0.0.1",
            path=self.url, data=data).json()
        suggestion = Suggestion.objects.filter(
            category=self.suggestion_category,
            description=self.valid_description
        ).first()
        assert suggestion
        assert not suggestion.allocated_by
        self.assertDictEqual(response, {
            'status': 'ok',
            'suggestion': {
                "id": suggestion.id,
                "priority": "یک",
                "title": "test",
                "description": self.valid_description,
                "name": None,
                "mobile": None,
                "email": 'test@gmail.com',
            },
        })

    def test_add_suggestion_with_not_valid_description(self):
        data = {
            'suggestionCategory': self.suggestion_category.id,
            'description': self.not_valid_description,
            'email': 'test@gmail.com',
        }
        response = self.client.post(
            REMOTE_ADDR="127.0.0.3",
            path=self.url, data=data).json()
        suggestion = Suggestion.objects.filter(
            category=self.suggestion_category,
            description=self.not_valid_description
        ).first()
        assert not suggestion
        self.assertDictEqual(response, {
            'status': 'failed',
            'code': 'ValidationError',
            'message': 'DescriptionValidationFailed',
        })
