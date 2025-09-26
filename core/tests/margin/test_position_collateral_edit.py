from decimal import Decimal
from typing import Optional
from unittest.mock import patch

from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from exchange.accounts.models import User
from exchange.base.models import Currencies
from exchange.margin.models import Position
from exchange.wallet.models import Wallet


class PositionCollateralEditBaseTest(APITestCase):
    user: User
    wallet: Wallet
    sell_position: Position
    buy_position: Position

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.get(pk=201)
        shared_data = {
            'user': cls.user,
            'src_currency': Currencies.btc,
            'dst_currency': Currencies.usdt,
            'status': Position.STATUS.open,
        }
        cls.wallet = Wallet.get_user_wallet(cls.user, Currencies.usdt, tp=Wallet.WALLET_TYPE.margin)
        cls.wallet.create_transaction('manual', '70').commit()
        cls.wallet.refresh_from_db()
        cls.sell_position = Position.objects.create(
            **shared_data,
            side=Position.SIDES.sell,
            delegated_amount='0.001',
            earned_amount='10',
            collateral='43.1',
            entry_price='21300',
        )
        cls.wallet.block(Decimal('43.1'))
        cls.buy_position = Position.objects.create(
            **shared_data,
            side=Position.SIDES.buy,
            leverage=2,
            delegated_amount='0.000999',
            earned_amount='-20',
            collateral='10',
            entry_price='20000',
        )
        cls.wallet.block(Decimal('10'))
        cache.set('market_{}_last_price'.format(cls.sell_position.market.id), Decimal('21200'))

    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.user.auth_token.key}')


class PositionCollateralEditAPITest(PositionCollateralEditBaseTest):

    def _test_successful_position_collateral_edit(
        self, position: Position, collateral: str, initial_margin_ratio: 'str'
    ):
        extra_blocked_balance = self.wallet.blocked_balance - Decimal(position.collateral)
        with patch('exchange.margin.models.Position.margin_ratio', Decimal(initial_margin_ratio)):
            response = self.client.post(f'/positions/{position.id}/edit-collateral', {'collateral': collateral})
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert 'position' in data
        assert data['position']['collateral'] == collateral
        assert data['position']['marginRatio'] == initial_margin_ratio
        assert data['position']['liquidationPrice']
        self.wallet.refresh_from_db()
        assert self.wallet.blocked_balance == extra_blocked_balance + Decimal(collateral)

        changes = position.collateral_changes.all()
        assert len(changes) == 1
        assert changes[0].old_value == Decimal(position.collateral)
        assert changes[0].new_value == Decimal(collateral)

    def _test_unsuccessful_position_collateral_edit(self, position_id: int, data: dict, code: str):
        response = self.client.post(f'/positions/{position_id}/edit-collateral', data)
        if code == 'NotFound':
            assert response.status_code == status.HTTP_404_NOT_FOUND
            return
        assert response.status_code == status.HTTP_400_BAD_REQUEST if code == 'ParseError' else status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'failed'
        assert data['code'] == code
        self.wallet.refresh_from_db()
        assert self.wallet.blocked_balance == Decimal('53.1')
        assert not self.sell_position.collateral_changes.exists()
        assert not self.buy_position.collateral_changes.exists()

    def test_position_collateral_edit_decrease_above_initial_ratio(self):
        self._test_successful_position_collateral_edit(self.sell_position, collateral='38', initial_margin_ratio='2.5')
        self._test_successful_position_collateral_edit(self.buy_position, collateral='9', initial_margin_ratio='2')

    def test_position_collateral_edit_decrease_below_initial_ratio(self):
        self._test_unsuccessful_position_collateral_edit(self.sell_position.id, {'collateral': '30'}, 'LowMarginRatio')
        self._test_unsuccessful_position_collateral_edit(self.buy_position.id, {'collateral': '5'}, 'LowMarginRatio')

    def test_position_collateral_edit_decrease_with_leverage(self):
        Position.objects.filter(pk=self.sell_position.pk).update(
            leverage=5, delegated_amount='0.005', earned_amount='50'
        )
        self._test_unsuccessful_position_collateral_edit(self.sell_position.id, {'collateral': '5'}, 'LowMarginRatio')
        self._test_successful_position_collateral_edit(self.sell_position, collateral='10', initial_margin_ratio='1.9')

    def test_position_collateral_edit_increase_sufficient_balance(self):
        self._test_successful_position_collateral_edit(self.sell_position, collateral='50', initial_margin_ratio='2.5')
        self._test_successful_position_collateral_edit(self.buy_position, collateral='15', initial_margin_ratio='2.5')

    def test_position_collateral_edit_take_out_all(self):
        self._test_successful_position_collateral_edit(self.sell_position, collateral='0', initial_margin_ratio='3.5')
        self._test_successful_position_collateral_edit(self.buy_position, collateral='0', initial_margin_ratio='3.5')

    def test_position_collateral_edit_increase_insufficient_balance(self):
        self._test_unsuccessful_position_collateral_edit(
            self.sell_position.id, {'collateral': '65'}, 'InsufficientBalance'
        )
        self._test_unsuccessful_position_collateral_edit(
            self.buy_position.id, {'collateral': '30'}, 'InsufficientBalance'
        )

    def test_position_collateral_edit_empty_margin_ratio(self):
        with patch('exchange.margin.models.Position.margin_ratio', None):
            self._test_unsuccessful_position_collateral_edit(
                self.sell_position.id, {'collateral': '30'}, 'TryAgainLater'
            )
            self._test_unsuccessful_position_collateral_edit(self.buy_position.id, {'collateral': '8'}, 'TryAgainLater')

    def test_position_collateral_edit_above_precision(self):
        assert self.sell_position.collateral == '43.1'
        assert self.buy_position.collateral == '10'
        assert self.wallet.blocked_balance == Decimal('53.1')
        with patch('exchange.margin.models.Position.margin_ratio', Decimal('2.5')):
            data = {'collateral': '38.00000000005'}
            response = self.client.post(f'/positions/{self.sell_position.id}/edit-collateral', data)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        position = Position.objects.get(pk=self.sell_position.pk)
        assert position.collateral == Decimal('38')
        self.wallet.refresh_from_db()
        assert self.wallet.blocked_balance == Decimal('48')

    def test_position_collateral_edit_invalid_input(self):
        self._test_unsuccessful_position_collateral_edit(self.buy_position.id + 1, {'collateral': '30'}, 'NotFound')
        self._test_unsuccessful_position_collateral_edit(self.sell_position.id, {'collateral': '-20'}, 'ParseError')


class PositionCollateralEditOptionsAPITest(PositionCollateralEditBaseTest):

    def _test_successful_position_collateral_options(
        self, position: Position, margin_ratio: Optional[str], min_collateral: str, max_collateral: str
    ):
        with patch('exchange.margin.models.Position.margin_ratio', Decimal(margin_ratio) if margin_ratio else None):
            response = self.client.get(f'/positions/{position.id}/edit-collateral/options')
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert 'collateral' in data
        assert data['collateral']['min'] == min_collateral
        assert data['collateral']['max'] == max_collateral

    def _test_unsuccessful_position_collateral_options(self, position_id: int):
        response = self.client.get(f'/positions/{position_id}/edit-collateral/options')
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_position_collateral_edit_options_in_profit(self):
        self._test_successful_position_collateral_options(
            self.sell_position, margin_ratio='2.5', min_collateral='32.48', max_collateral='60'
        )
        self._test_successful_position_collateral_options(
            self.buy_position, margin_ratio='1.8', min_collateral='4.81', max_collateral='26.9'
        )

    def test_position_collateral_edit_options_in_loss(self):
        self._test_successful_position_collateral_options(
            self.sell_position, margin_ratio='1.8', min_collateral='43.1', max_collateral='60'
        )
        self._test_successful_position_collateral_options(
            self.buy_position, margin_ratio='1.3', min_collateral='10', max_collateral='26.9'
        )

    def test_position_collateral_edit_options_empty_margin_ratio(self):
        self._test_successful_position_collateral_options(
            self.sell_position, margin_ratio=None, min_collateral='43.1', max_collateral='60'
        )
        self._test_successful_position_collateral_options(
            self.buy_position, margin_ratio=None, min_collateral='10', max_collateral='26.9'
        )

    def test_position_collateral_edit_options_with_other_blocked_balances(self):
        self.wallet.block(Decimal(10))
        self._test_successful_position_collateral_options(
            self.sell_position, margin_ratio='2', min_collateral='43.1', max_collateral='50'
        )
        self._test_successful_position_collateral_options(
            self.buy_position, margin_ratio='1.5', min_collateral='10', max_collateral='16.9'
        )

    def test_position_collateral_options_invalid_input(self):
        self._test_unsuccessful_position_collateral_options(self.sell_position.id - 1)


class PredictCollateralEditAPITest(PositionCollateralEditBaseTest):

    def _test_successful_position_collateral_edit_predict(
        self, position: Position, change: str, collateral: str, margin_ratio: str, liquidation_price: str
    ):
        change = Decimal(change)
        response = self.client.get('/margin/predict/edit-collateral', {
            'positionId': position.id, 'add' if change > 0 else 'sub': abs(change),
        })
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['status'] == 'ok'
        assert data['collateral'] == collateral
        assert data['marginRatio'] == margin_ratio
        assert data['liquidationPrice'] == liquidation_price
        position.refresh_from_db()
        assert Decimal(collateral) != position.collateral

    def _test_unsuccessful_position_collateral_edit_predict(self, data: dict, code: str):
        response = self.client.get('/margin/predict/edit-collateral', data)
        if code == 'NotFound':
            assert response.status_code == status.HTTP_404_NOT_FOUND
        else:
            assert response.status_code == status.HTTP_400_BAD_REQUEST
            data = response.json()
            assert data['status'] == 'failed'
            assert data['code'] == code

    def test_position_collateral_edit_predict_on_increase(self):
        self._test_successful_position_collateral_edit_predict(
            self.sell_position, change='5', collateral='48.1', margin_ratio='2.73', liquidation_price='52749.52'
        )
        self._test_successful_position_collateral_edit_predict(
            self.buy_position, change='5', collateral='15', margin_ratio='1.8', liquidation_price='7007.01'
        )

    def test_position_collateral_edit_predict_on_decrease(self):
        self._test_successful_position_collateral_edit_predict(
            self.sell_position, change='-10', collateral='33.1', margin_ratio='2.03', liquidation_price='39130.88'
        )
        self._test_successful_position_collateral_edit_predict(
            self.buy_position, change='-1', collateral='9', margin_ratio='1.5', liquidation_price='13013.01'
        )

    def test_position_collateral_edit_predict_invalid_input(self):
        pid = self.sell_position.id
        self._test_unsuccessful_position_collateral_edit_predict({}, 'ParseError')
        self._test_unsuccessful_position_collateral_edit_predict({'positionId': -1, 'add': '4'}, 'NotFound')
        self._test_unsuccessful_position_collateral_edit_predict({'positionId': pid}, 'ParseError')
        self._test_unsuccessful_position_collateral_edit_predict({'positionId': pid, 'add': '0'}, 'ParseError')
        self._test_unsuccessful_position_collateral_edit_predict({'positionId': pid, 'sub': '-5'}, 'ParseError')
