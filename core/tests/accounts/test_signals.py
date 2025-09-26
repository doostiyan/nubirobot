from django.test import TestCase

from exchange.accounts.constants import new_tags
from exchange.accounts.models import Tag, User, VerificationRequest


class SignalsTest(TestCase):

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = User.objects.create_user(username='test-user')

    def test_remove_incomplete_documents_tag(self):
        tag, _ = Tag.objects.get_or_create(
            tp=Tag.TYPES.kyc,
            name=new_tags.get('incomplete_documents'),
        )

        self.user.tags.add(tag)

        assert self.user.tags.filter(name=new_tags.get('incomplete_documents')).exists()

        VerificationRequest.objects.create(
            user=self.user,
            tp=VerificationRequest.TYPES.address,
        )

        assert not self.user.tags.filter(name=new_tags.get('incomplete_documents')).exists()
