from django.test import TestCase
from rest_framework import status

from tests.staking.utils import PlanTestDataMixin


class PlanOffersAPITests(PlanTestDataMixin, TestCase):
    URL = '/earn/plan/offers'

    def setUp(self) -> None:
        self.plan = self.create_plan(**self.get_plan_kwargs())

    def test_response_data_is_empty_when_not_having_offer_plans(self):
        response = self.client.get(self.URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'hasNext': False,
            'result': [],
            'status': 'ok',
        }

    def test_response_data_is_empty_when_having_offer_plans(self):
        self.plan.is_offer = True
        self.plan.save(update_fields=['is_offer'])

        response = self.client.get(self.URL)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            'hasNext': False,
            'result': [],
            'status': 'ok',
        }
