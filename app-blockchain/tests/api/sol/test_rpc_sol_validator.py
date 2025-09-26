import pytest

from exchange.blockchain.api.sol.rpc_sol import RpcSolValidator


@pytest.fixture
def valid_program_id_account_key() -> dict:
    return {'pubkey': RpcSolValidator.valid_program_id}


def test__validate_transaction_account_keys__last_account_system_program__return_true(
        valid_program_id_account_key: dict):
    assert RpcSolValidator.validate_transaction_account_keys([valid_program_id_account_key])


@pytest.mark.parametrize('valid_pub_key', ['ComputeBudget111111111111111111111111111111',
                                           'Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo',
                                           'MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr', ])
def test__validate_transaction_account_keys__last_account_in_valid_list_and_before_last_system_program__return_true(
        valid_pub_key: str, valid_program_id_account_key: dict):
    assert RpcSolValidator.validate_transaction_account_keys([valid_program_id_account_key, {'pubkey': valid_pub_key}])


def test__validate_transaction_account_keys__last_account_not_in_valid_list_and_before_last_system_program__return_false(
        valid_program_id_account_key: dict):
    assert not RpcSolValidator.validate_transaction_account_keys([valid_program_id_account_key, {'pubkey': 'bad'}])


def test__validate_transaction_account_keys__no_system_program_and_count_of_accounts_less_than_3__return_false():
    assert not RpcSolValidator.validate_transaction_account_keys([{'pubkey': 'some_key'}, {'pubkey': 'another_key'}])


def test__validate_transaction_account_keys__no_system_program_in_last_three_accounts__when_more_than_2__return_false():
    assert not RpcSolValidator.validate_transaction_account_keys(
        [{'pubkey': 'some_key'}, {'pubkey': 'another_key'}, {'pubkey': 'another_key'}])


def test__validate_transaction_account_keys__system_program_in_three_accounts_to_end_but_the_sysvar_and_compute_budget_condition_not_met__return_false(
        valid_program_id_account_key: dict):
    assert not RpcSolValidator.validate_transaction_account_keys(
        [
            valid_program_id_account_key,
            {'pubkey': 'ComputeBudget111111111111111111111111111112'},
            {'pubkey': 'SysvarRecentB1ockHashes11111111111111111111'}
        ])

def test__validate_transaction_account_keys__system_program_in_three_accounts_to_end_but_the_sysvar_and_compute_budget_condition_met__return_true(
        valid_program_id_account_key: dict):
    assert RpcSolValidator.validate_transaction_account_keys(
        [
            valid_program_id_account_key,
            {'pubkey': 'ComputeBudget111111111111111111111111111111'},
            {'pubkey': 'SysvarRecentB1ockHashes11111111111111111111'}
        ])
