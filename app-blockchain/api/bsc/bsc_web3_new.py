import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple, Union

from exchange.base.models import Currencies
from exchange.blockchain.api.commons.staking_reward import StakingRewardApi, StakingRewardParser
from exchange.blockchain.api.commons.web3 import Web3Api, Web3ResponseParser
from exchange.blockchain.api.general.dtos.get_validator_description_response import GetValidatorDescriptionResponse
from exchange.blockchain.api.general.dtos.get_validator_info_response import GetValidatorInfoResponse, ValidatorStatus
from exchange.blockchain.contracts_conf import BEP20_contract_currency, BEP20_contract_info
from exchange.blockchain.utils import BlockchainUtilsMixin


class BSCWeb3Parser(Web3ResponseParser, StakingRewardParser):
    precision = 18
    symbol = 'BNB'
    currency = Currencies.bnb
    STAKING_CONTRACT_ADDRESS = '0x0000000000000000000000000000000000002002'
    OPERATOR_ADDRESS_INPUT_LENGTH = 74

    @classmethod
    def contract_currency_list(cls) -> Optional[Dict[str, Any]]:
        return BEP20_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls) -> Optional[Dict[str, Any]]:
        return BEP20_contract_info.get(cls.network_mode)

    @classmethod
    def parse_get_validator_info(cls,
                                 response: Tuple[int, bool, int],
                                 is_address_in_validators: bool) -> GetValidatorInfoResponse:
        status = ValidatorStatus.IN_ACTIVE
        if response[1]:
            status = ValidatorStatus.JAILED
        elif is_address_in_validators:
            status = ValidatorStatus.ACTIVE

        return GetValidatorInfoResponse(
            status=status,
            jail_until=datetime.fromtimestamp(response[2], tz=timezone.utc).isoformat(),
            created_time=datetime.fromtimestamp(response[0], tz=timezone.utc).isoformat(),
        )

    @classmethod
    def parse_get_validator_total_stake_from_contract(cls, response: Union[int, Decimal]) -> Decimal:
        return Decimal(str(response))

    @classmethod
    def parse_get_validator_description(cls,
                                        response: Dict[str, Any]
                                        ) -> GetValidatorDescriptionResponse:
        return GetValidatorDescriptionResponse(
            validator_name=response[0],
            website=response[2],
        )

    @classmethod
    def parse_get_validator_commission(cls, response: int) -> Decimal:
        return Decimal(str(response))

    @classmethod
    def parse_get_all_operator_addresses(cls, response: List[str]) -> List[str]:
        return response

    @classmethod
    def parse_get_txs_staked_balance(cls, response: any) -> Tuple[Decimal, List[str]]:
        staked_amount = Decimal(0)
        operator_addresses = []

        for tx in response.get('result', []):
            if tx['to'].lower() == cls.STAKING_CONTRACT_ADDRESS.lower():
                staked_amount += BlockchainUtilsMixin.from_unit(int(tx['value']), precision=cls.precision)
                if len(tx['input']) >= cls.OPERATOR_ADDRESS_INPUT_LENGTH:
                    operator_address = '0x' + tx['input'][34:cls.OPERATOR_ADDRESS_INPUT_LENGTH]
                    operator_addresses.append(operator_address)
            elif tx['from'].lower() == cls.STAKING_CONTRACT_ADDRESS.lower():
                staked_amount -= BlockchainUtilsMixin.from_unit(int(tx['value']), precision=cls.precision)

        return max(staked_amount, Decimal(0)), [BSCWeb3Api().to_checksum_address(addr) for addr in operator_addresses]


class BSCWeb3Api(Web3Api, StakingRewardApi):
    parser = BSCWeb3Parser
    block_height_offset = 20
    cache_key = 'bsc'
    symbol = 'BNB'
    _base_url = 'https://bsc.publicnode.com'
    simple_staking_contract_abi = [
        {'type': 'function', 'name': 'getValidatorTotalPooledBNBRecord',
         'inputs': [{'name': 'operatorAddress', 'type': 'address', 'internalType': 'address'},
                    {'name': 'index', 'type': 'uint256', 'internalType': 'uint256'}],
         'outputs': [{'name': '', 'type': 'uint256', 'internalType': 'uint256'}], 'stateMutability': 'view'},
        {'type': 'function', 'name': 'getValidatorBasicInfo',
         'inputs': [{'name': 'operatorAddress', 'type': 'address', 'internalType': 'address'}],
         'outputs': [{'name': 'createdTime', 'type': 'uint256', 'internalType': 'uint256'},
                     {'name': 'jailed', 'type': 'bool', 'internalType': 'bool'},
                     {'name': 'jailUntil', 'type': 'uint256', 'internalType': 'uint256'}], 'stateMutability': 'view'},
        {'type': 'function', 'name': 'getValidators',
         'inputs': [{'name': 'offset', 'type': 'uint256', 'internalType': 'uint256'},
                    {'name': 'limit', 'type': 'uint256', 'internalType': 'uint256'}],
         'outputs': [{'name': 'operatorAddrs', 'type': 'address[]', 'internalType': 'address[]'},
                     {'name': 'creditAddrs', 'type': 'address[]', 'internalType': 'address[]'},
                     {'name': 'totalLength', 'type': 'uint256', 'internalType': 'uint256'}], 'stateMutability': 'view'},
        {'type': 'function', 'name': 'getValidatorDescription',
         'inputs': [{'name': 'operatorAddress', 'type': 'address', 'internalType': 'address'}], 'outputs': [
            {'name': '', 'type': 'tuple', 'internalType': 'struct StakeHub.Description',
             'components': [{'name': 'moniker', 'type': 'string', 'internalType': 'string'},
                            {'name': 'identity', 'type': 'string', 'internalType': 'string'},
                            {'name': 'website', 'type': 'string', 'internalType': 'string'},
                            {'name': 'details', 'type': 'string', 'internalType': 'string'}]}],
         'stateMutability': 'view'},
        {'type': 'function', 'name': 'getValidatorCommission',
             'inputs': [{'name': 'operatorAddress', 'type': 'address', 'internalType': 'address'}], 'outputs': [
            {'name': '', 'type': 'tuple', 'internalType': 'struct StakeHub.Commission',
             'components': [{'name': 'rate', 'type': 'uint64', 'internalType': 'uint64'},
                            {'name': 'maxRate', 'type': 'uint64', 'internalType': 'uint64'},
                            {'name': 'maxChangeRate', 'type': 'uint64', 'internalType': 'uint64'}]}],
         'stateMutability': 'view'}
    ]

    def __init__(self) -> None:
        from web3.middleware import ExtraDataToPOAMiddleware
        super().__init__()
        self.web3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        self.staking_contract = self.web3.eth.contract(
            address=self.parser.STAKING_CONTRACT_ADDRESS,
            abi=self.simple_staking_contract_abi
        )

    def get_validator_total_stake_from_contract(self, operator_address: str) -> Union[int, Decimal]:
        current_timestamp = int(time.time())
        index = (current_timestamp // 86400) - 1
        checksum_operator_address = self.to_checksum_address(operator_address)
        stake_amount = self.staking_contract.functions.getValidatorTotalPooledBNBRecord(checksum_operator_address,
                                                                                        index).call()
        return BlockchainUtilsMixin.from_unit(stake_amount, precision=self.parser.precision)

    def get_validator_info(self, operator_address: str) -> Tuple[int, bool, int]:
        checksum_operator_address = self.to_checksum_address(operator_address)
        return self.staking_contract.functions.getValidatorBasicInfo(checksum_operator_address).call()

    def get_validator_description(self, operator_address: str) -> Dict[str, Any]:
        checksum_operator_address = self.to_checksum_address(operator_address)
        return self.staking_contract.functions.getValidatorDescription(checksum_operator_address).call()

    def get_validator_commission(self, operator_address: str) -> int:
        checksum_operator_address = self.to_checksum_address(operator_address)
        rate, _, _ = self.staking_contract.functions.getValidatorCommission(checksum_operator_address).call()
        return rate

    def get_all_operator_addresses(self, offset: int, limit: int) -> List[str]:
        operator_addresses, _, _ = self.staking_contract.functions.getValidators(offset, limit).call()
        return operator_addresses

    def to_checksum_address(self, address: str) -> str:
        return self.web3.to_checksum_address(address)
