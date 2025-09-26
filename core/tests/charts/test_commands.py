from django.core.management import call_command
from django.test import TestCase

from exchange.accounts.models import User
from exchange.charts.models import Chart, StudyTemplate


class FillUserIdOfChartsCommandTestCase(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user1: User = User.objects.get(pk=201)

        cls.user2 = User.objects.get(pk=202)
        cls.user3 = User.objects.get(pk=203)

        # ownerId is chat_id
        cls.chart1 = Chart.objects.create(
            ownerId=cls.user1.chat_id.hex,
            ownerSource='nobitex',
            symbol='BTCIRT',
            lastModified='2024-06-12',
        )

        # ownerId is user_id
        cls.chart2 = Chart.objects.create(
            ownerId=f'{cls.user2.id}', ownerSource='nobitex', symbol='USDTIRT', lastModified='2024-06-12'
        )

        # invalid ownerId
        cls.chart3 = Chart.objects.create(
            ownerId='public', ownerSource='nobitex', symbol='USDTIRT', lastModified='2024-06-12'
        )

        # invalid ownerId
        cls.chart4 = Chart.objects.create(
            ownerId='326574', ownerSource='nobitex', symbol='USDTIRT', lastModified='2024-06-12'
        )

    def test_fill_user_id(self):
        assert self.chart1.user_id is None
        assert self.chart2.user_id is None
        assert self.chart3.user_id is None
        assert self.chart4.user_id is None

        call_command('fill_user_id_of_charts', batch_size=500)

        # to delete charts that have no user_id
        call_command('fill_user_id_of_charts', batch_size=500, delete_empty_users=True)

        self.chart1.refresh_from_db()
        self.chart2.refresh_from_db()
        #
        # # User Ids must be filled correctly
        assert self.chart1.user_id == self.user1.id
        assert self.chart2.user_id == self.user2.id

        charts_count = Chart.objects.count()

        assert charts_count == 2

        # Invalid char must be deleted
        assert Chart.objects.filter(id=self.chart3.id).count() == 0
        assert Chart.objects.filter(id=self.chart4.id).count() == 0


class FillUserIdOfStudyTemplatesCommandTestCase(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.user1, _ = User.objects.get_or_create(pk=201)
        cls.user2, _ = User.objects.get_or_create(pk=202)
        # cls.user3 = User.objects.get(pk=203)

        # ownerId is chat_id
        cls.stdtmpl1 = StudyTemplate.objects.create(
            ownerId=cls.user1.chat_id.hex,
            ownerSource='nobitex',
            name='tmpl1',
        )

        # ownerId is user_id
        cls.stdtmpl2 = StudyTemplate.objects.create(
            ownerId=str(cls.user2.id),
            ownerSource='nobitex',
            name='tmpl2',
        )

        # invalid ownerId
        cls.stdtmpl3 = StudyTemplate.objects.create(
            ownerId='blahblahblah',
            ownerSource='nobitex',
            name='tmpl3',
        )
        cls.stdtmpl4 = StudyTemplate.objects.create(
            ownerId='-1',
            ownerSource='nobitex',
            name='tmpl4',
        )

        # special case
        cls.stdtmpl5 = StudyTemplate.objects.create(
            ownerId='aee968bae9fc49eab103cde3fa2b5b18',
            ownerSource='nobitex',
            name='tmpl5',
        )

    def test_fill_user_id(self):
        call_command('fill_user_id_of_study_templates')

        self.stdtmpl1.refresh_from_db()
        self.stdtmpl2.refresh_from_db()
        self.stdtmpl3.refresh_from_db()
        self.stdtmpl4.refresh_from_db()
        self.stdtmpl5.refresh_from_db()

        assert self.stdtmpl1.user == self.user1
        assert self.stdtmpl2.user == self.user2
        assert self.stdtmpl3.user is None
        assert self.stdtmpl4.user is None
        assert self.stdtmpl5.user is None

        call_command('fill_user_id_of_study_templates', delete_empty_users=True)

        assert StudyTemplate.objects.count() == 3
        assert StudyTemplate.objects.filter(user__isnull=False).count() == 2
