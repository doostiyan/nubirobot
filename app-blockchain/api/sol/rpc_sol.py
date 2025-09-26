import json
import random
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from django.conf import settings

from exchange.base.parsers import parse_utc_timestamp
from exchange.blockchain.api.general.dtos import Balance, TransferTx
from exchange.blockchain.api.general.general import GeneralApi, ResponseParser, ResponseValidator
from exchange.blockchain.contracts_conf import SPLTOKEN_contract_currency, sol_contract_info
from exchange.blockchain.utils import BlockchainUtilsMixin

if settings.BLOCKCHAIN_CACHE_PREFIX == 'cold_':
    from wallet.models import CURRENCIES as Currencies
else:
    from exchange.base.models import Currencies


class RpcSolValidator(ResponseValidator):
    min_valid_tx_amount = Decimal('0.001')
    valid_program_id = '11111111111111111111111111111111'
    valid_program_token_id = ['TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA']
    valid_instruction_types = ['transfer', 'transferChecked']

    precision = 9
    MINIMUM_REQUIRED_ACCOUNTS_COUNT = 2

    @classmethod
    def validate_general_response(cls, response: dict) -> bool:
        if not response:
            return False
        if not response.get('result'):
            return False
        return True

    @classmethod
    def validate_balance_response(cls, balance_response: dict) -> bool:
        if (cls.validate_general_response(balance_response)
                and balance_response.get('result').get('value')):
            return True
        return False

    @classmethod
    def validate_balances_response(cls, balances_response: dict) -> bool:
        if (cls.validate_general_response(balances_response)
                and balances_response.get('result').get('value')):
            return True
        return False

    @classmethod
    def validate_block_head_response(cls, block_head_response: dict) -> bool:
        if (cls.validate_general_response(block_head_response)
                and block_head_response.get('result').get('absoluteSlot')):
            return True
        return False

    @classmethod
    def validate_tx_details_response(cls, tx_details_response: dict) -> bool:
        return cls.validate_general_response(tx_details_response)

    @classmethod
    def validate_address_txs_response(cls, address_txs_response: list) -> bool:
        if address_txs_response:
            return True
        return False

    @classmethod
    def validate_block_txs_response(cls, block_txs_response: list) -> bool:
        if block_txs_response:
            return True
        return False

    @classmethod
    def validate_block(cls, block: dict) -> bool:
        if (type(block) is str
                or block.get('error')
                or not block.get('result')
                or not block.get('result').get('transactions')):
            return False
        return True

    @classmethod
    def validate_transaction(cls, transaction: dict) -> bool:
        if (not transaction
                or not transaction.get('meta')
                or transaction.get('meta').get('err')
                or transaction.get('meta').get('status').get('Err')
                or 'Ok' not in transaction.get('meta').get('status')
                or transaction.get('transaction').get('message').get('accountKeys')[0].get('pubkey').casefold() ==
                transaction.get('transaction').get('message').get('accountKeys')[1].get('pubkey').casefold()
                or not transaction.get('transaction').get('signatures')): # not empty tx_hash

            return False

        account_keys = transaction.get('transaction').get('message').get('accountKeys')
        if not cls.validate_transaction_account_keys(account_keys):
            return False
        return True

    @classmethod
    def validate_block_transaction(cls, transaction: dict) -> bool:
        if (transaction.get('meta').get('err')
                or transaction.get('meta').get('status').get('Err')
                or 'Ok' not in transaction.get('meta').get('status')
                or not transaction.get('transaction').get('signatures')  # not empty tx_hash
                or not transaction.get('transaction').get('accountKeys')
                or len(transaction.get('transaction').get('accountKeys')) < cls.MINIMUM_REQUIRED_ACCOUNTS_COUNT
                or transaction.get('transaction').get('accountKeys')[0].get('pubkey').casefold() ==
                transaction.get('transaction').get('accountKeys')[1].get('pubkey').casefold()
        ):
            return False

        # Check the address of the transaction's program. If address
        # is not the valid address "11111111111111111111111111111111",
        # consider the transaction invalid.
        account_keys = transaction.get('transaction').get('accountKeys')
        if not cls.validate_transaction_account_keys(account_keys):
            return False
        return True

    @classmethod
    def validate_token_block_transaction(cls, transaction: dict) -> bool:
        if not transaction or not isinstance(transaction, dict):
            return False
        if not transaction.get('meta') or not isinstance(transaction.get('meta'), dict):
            return False
        if (transaction.get('meta').get('err')
                or transaction.get('meta').get('status').get('Err')
                or not transaction.get('meta').get('status')
                or 'Ok' not in transaction.get('meta').get('status')
                or not transaction.get('transaction').get('signatures')
                or not transaction.get('transaction').get('accountKeys')
        ):
            return False
        return True

    @classmethod
    def validate_transaction_account_keys(cls, account_keys: List[Dict[str, any]]) -> bool:
        compute_budget_program_id = 'ComputeBudget111111111111111111111111111111'
        sys_recent_block_hashes_program_id = 'SysvarRecentB1ockHashes11111111111111111111'
        memo_program_v1 = 'Memo1UhkJRfHyvLMcVucJwxXeuD728EqVDDwQDxFMNo'
        memo_program_v2 = 'MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr'
        blo_xroute_memo_program = 'HQ2UUt18uJqKaQFJhgV9zaTdQxUZjNrsKFgoEDquBkcx'

        # This list below is for valid patterns, which usually includes our deposits.
        # If it is a new pattern, it should be added to this list after testing.
        valid_account_key_patterns = [
            ''.join(account_address) for account_address in
            [
                (cls.valid_program_id,),
                (cls.valid_program_id, memo_program_v1),
                (cls.valid_program_id, memo_program_v2),
                (cls.valid_program_id, compute_budget_program_id),
                (cls.valid_program_id, compute_budget_program_id, sys_recent_block_hashes_program_id),
                (cls.valid_program_id, compute_budget_program_id, blo_xroute_memo_program),
            ]
        ]

        tx_account_keys_str = ''.join([account_key.get('pubkey') for account_key in account_keys])

        if not any(
                tx_account_keys_str.endswith(pattern)
                for pattern in valid_account_key_patterns
        ):
            return False
        return True

    @classmethod
    def validate_block_transactions_transfer_value(cls, value: int) -> bool:
        """
        This is a method to validate transfers of a multi transfer transaction value.
        :return:
        """
        if value < 0:
            return False

        value = BlockchainUtilsMixin.from_unit(value, cls.precision)

        if value < cls.min_valid_tx_amount:
            return False
        return True

    @classmethod
    def validate_transfer(cls, transfer: dict) -> bool:
        if not any(transfer.get(key) for key in ('parsed', 'program', 'programId')):
            return False
        # Check the name and address of the transaction's program
        # If the program name is not "system" or the address
        # is not the valid address "11111111111111111111111111111111",
        # consider the transaction invalid.
        if (transfer.get('program') != 'system'
                or transfer.get('programId') != cls.valid_program_id
                or not transfer.get('parsed')
                or not transfer.get('parsed').get('info')
                or not transfer.get('parsed').get('info').get('lamports')
                or BlockchainUtilsMixin.from_unit(transfer.get('parsed').get('info').get('lamports'),
                                                  precision=cls.precision) < cls.min_valid_tx_amount
                or not transfer.get('parsed').get('type')
                or transfer.get('parsed').get('type') not in ['transfer', 'transferChecked']
                or transfer.get('parsed').get('info').get('source').casefold() ==
                transfer.get('parsed').get('info').get('destination').casefold()
        ):
            return False
        return True

    @classmethod
    def validate_token_transaction(cls, transaction: dict) -> bool:
        """
        Validates if a transaction signature entry from getSignaturesForAddress is valid.

        Args:
            transaction: Dict containing transaction signature information

        Returns:
            bool: True if the transaction entry is valid, False otherwise
        """
        if not transaction:
            return False

        required_fields = ['blockTime', 'transaction', 'meta', 'slot']
        if not all(field in transaction for field in required_fields):
            return False

        if transaction.get('err') is not None:
            return False

        if transaction.get('meta') is None:
            return False

        if not transaction.get('transaction').get('signatures'):
            return False

        if not transaction.get('transaction').get('message'):
            return False

        if not transaction.get('transaction').get('message').get('instructions'):
            return False

        if not isinstance(transaction.get('blockTime'), (int, float)):
            return False

        if not isinstance(transaction.get('slot'), int):
            return False

        return True

    @classmethod
    def validate_instruction(cls, instruction: dict) -> bool:
        if (
                instruction.get('programId') in cls.valid_program_token_id
                and instruction.get('program') == 'spl-token'
                and instruction.get('parsed')
                and instruction.get('parsed', {}).get('type') in cls.valid_instruction_types
        ):
            return True

        return False

    @classmethod
    def validate_logs(cls, logs: List[str]) -> bool:
        """
        Validates whether a swap or burn instruction is NOT present in the log messages.
        Only checks for exact matches.

        Args:
            logs (List[str]): The transaction log messages from Solana.

        Returns:
            bool: False if a 'swap' or 'burn' instruction is found exactly, True otherwise.
        """
        forbidden_logs = {
            'Program log: Instruction: Swap',
            'Program log: Instruction: SwapV2',
            'Program log: Instruction: BurnChecked'
        }

        return all(log not in forbidden_logs for log in logs)


class RpcSolParser(ResponseParser):
    validator = RpcSolValidator
    precision = 9
    symbol = 'SOL'
    currency = Currencies.sol

    @classmethod
    def contract_currency_list(cls) -> Dict[str, int]:
        return SPLTOKEN_contract_currency.get(cls.network_mode)

    @classmethod
    def contract_info_list(cls) -> Dict[int, Dict[str, Union[str, int]]]:
        return sol_contract_info.get(cls.network_mode)

    @classmethod
    def parse_balance_response(cls, balance_response: dict) -> Decimal:
        return BlockchainUtilsMixin.from_unit(balance_response.get('result').get('value'), precision=cls.precision) \
            if cls.validator.validate_balance_response(balance_response) else Decimal(0)

    @classmethod
    def parse_balances_response(cls, balances_response: dict) -> List[Balance]:
        if not cls.validator.validate_balances_response(balances_response):
            return []
        balances = []
        for balance in balances_response.get('result').get('value'):
            balances.append(
                Balance(
                    balance=BlockchainUtilsMixin.from_unit(balance.get('lamports'),
                                                           cls.precision) if balance else Decimal('0')
                )
            )
        return balances

    @classmethod
    def parse_block_head_response(cls, block_head_response: dict) -> Optional[int]:
        return int(block_head_response.get('result').get('absoluteSlot')) \
            if cls.validator.validate_block_head_response(block_head_response) else None

    @classmethod
    def parse_txs_hash_response(cls, txs_hash_response: dict) -> list:
        return [
            tx_sig['signature']
            for tx_sig in txs_hash_response.get('result')
            if not tx_sig.get('err')
        ] if cls.validator.validate_general_response(txs_hash_response) else []

    @classmethod
    def parse_tx_details_response(cls, tx_details_response: dict, block_head: int) -> List[TransferTx]:
        return [
            TransferTx(
                block_height=tx_details_response.get('result').get('slot'),
                block_hash=None,
                tx_hash=tx_details_response.get('result').get('transaction').get('signatures')[0],
                date=parse_utc_timestamp(tx_details_response.get('result').get('blockTime')),
                success=True,
                confirmations=block_head - tx_details_response.get('result').get('slot'),
                from_address=transfer.get('parsed').get('info').get('source'),
                to_address=transfer.get('parsed').get('info').get('destination'),
                value=BlockchainUtilsMixin.from_unit(transfer.get('parsed').get('info').get('lamports'),
                                                     precision=cls.precision),
                symbol=cls.symbol,
                memo=None,
                tx_fee=BlockchainUtilsMixin.from_unit(tx_details_response.get('result').get('meta').get('fee'),
                                                      precision=cls.precision),
                token=None,
            )
            for transfer in tx_details_response.get('result').get('transaction').get('message').get('instructions')
            if cls.validator.validate_transfer(transfer)
        ] if (cls.validator.validate_tx_details_response(tx_details_response)
              and cls.validator.validate_transaction(tx_details_response.get('result'))) else []

    @classmethod
    def parse_address_txs_response(cls, address: str, address_txs_response: List[dict],
                                   block_head: int) -> List[TransferTx]:
        if not cls.validator.validate_address_txs_response(address_txs_response):
            return []
        transfers = []
        for tx in address_txs_response:
            if not cls.validator.validate_transaction(tx.get('result')):
                continue
            for transfer in tx.get('result').get('transaction').get('message').get('instructions'):
                if not cls.validator.validate_transfer(transfer):
                    continue

                from_address = transfer.get('parsed').get('info').get('source')
                to_address = transfer.get('parsed').get('info').get('destination')

                if address not in (from_address, to_address):
                    continue

                transfers.append(
                    TransferTx(
                        block_height=tx.get('result').get('slot'),
                        block_hash=None,
                        tx_hash=tx.get('result').get('transaction').get('signatures')[0],
                        date=parse_utc_timestamp(tx.get('result').get('blockTime')),
                        success=True,
                        confirmations=block_head - tx.get('result').get('slot'),
                        from_address=from_address,
                        to_address=to_address,
                        value=BlockchainUtilsMixin.from_unit(transfer.get('parsed').get('info').get('lamports'),
                                                             precision=cls.precision),
                        symbol=cls.symbol,
                        memo=None,
                        tx_fee=BlockchainUtilsMixin.from_unit(tx.get('result').get('meta').get('fee'),
                                                              precision=cls.precision),
                        token=None,
                    )
                )
        return transfers
    @classmethod
    def _parse_native_sol_transfers(
            cls, tx: dict, block_height: int, timestamp: Any, tx_hash: str
    ) -> List[TransferTx]:
        """
        Extract native SOL transfers from a transaction.
        Returns:
            List of native SOL transfer transactions
        """
        transfers = []
        transaction = tx.get('transaction', {})
        meta = tx.get('meta', {})
        account_keys = transaction.get('accountKeys', [])

        pre_balances = meta.get('preBalances', [])
        post_balances = meta.get('postBalances', [])

        if pre_balances and post_balances and len(pre_balances) == len(account_keys):
            sender = (
                account_keys[0].get('pubkey')
                if account_keys and isinstance(account_keys[0], dict)
                else None
            )
            for i in range(1, len(account_keys)):
                key_info = account_keys[i]
                recipient = key_info.get('pubkey')
                # Skip known system accounts.
                if recipient in [
                    '11111111111111111111111111111111',
                    'ComputeBudget111111111111111111111111111111',
                ]:
                    continue

                raw_value = post_balances[i] - pre_balances[i]
                if not cls.validator.validate_block_transactions_transfer_value(
                        raw_value
                ):
                    continue

                value = BlockchainUtilsMixin.from_unit(
                    raw_value, precision=cls.precision
                )
                transfers.append(
                    TransferTx(
                        block_height=block_height,
                        block_hash=None,
                        tx_hash=tx_hash,
                        date=timestamp,
                        success=True,
                        confirmations=None,
                        from_address=sender,
                        to_address=recipient,
                        value=value,
                        symbol=cls.symbol,
                        memo=None,
                        tx_fee=None,
                        token=None,
                    )
                )
        return transfers

    @classmethod
    def _parse_spl_token_transfers(
            cls, tx: dict, block_height: int, timestamp: Any, tx_hash: str
    ) -> List[TransferTx]:
        """
        Extract SPL token transfers from a transaction.
        Returns:
            List of SPL token transfer transactions
        """
        transfers = []
        meta = tx.get('meta', {})

        pre_token_balances = meta.get('preTokenBalances', [])
        post_token_balances = meta.get('postTokenBalances', [])
        if not pre_token_balances and not post_token_balances:
            return transfers
        pre_balances_map = {
            b.get('accountIndex'): b for b in pre_token_balances
        }
        post_balances_map = {
            b.get('accountIndex'): b for b in post_token_balances
        }
        token_mints = set()
        for balance in pre_token_balances + post_token_balances:
            if balance.get('mint'):
                token_mints.add(balance.get('mint'))

        if not token_mints or len(token_mints) > 1:
            return transfers
        processed_mints = set()
        for _post_idx, post_balance in post_balances_map.items():  # noqa: PERF102
            mint = post_balance.get('mint')
            if not mint or mint in processed_mints:
                continue

            currency = cls.contract_currency_list().get(mint)
            if not currency:
                continue

            contract_info = cls.contract_info_list().get(currency)
            if not contract_info:
                continue

            for p_idx, p_balance in post_balances_map.items():
                if p_balance.get('mint') != mint:
                    continue

                post_amount = int(p_balance.get('uiTokenAmount', {}).get('amount', '0'))
                pre_amount = 0

                if p_idx in pre_balances_map:
                    pre_amount = int(pre_balances_map[p_idx].get('uiTokenAmount', {}).get('amount', '0'))
                if post_amount <= pre_amount:
                    continue

                amount = post_amount - pre_amount
                recipient = p_balance.get('owner')

                sender = None
                for pre_idx, pre_balance in pre_balances_map.items():
                    if pre_balance.get('mint') != mint:
                        continue
                    pre_value = int(pre_balance.get('uiTokenAmount', {}).get('amount', '0'))
                    post_value = 0
                    if pre_idx in post_balances_map:
                        post_value = int(post_balances_map[pre_idx].get('uiTokenAmount', {}).get('amount', '0'))
                    if pre_value > post_value:
                        sender = pre_balance.get('owner')
                        break

                if not sender or sender == recipient:
                    continue
                value = BlockchainUtilsMixin.from_unit(amount, precision=contract_info.get('decimals'))
                transfers.append(
                    TransferTx(
                        block_height=block_height,
                        block_hash=None,
                        tx_hash=tx_hash,
                        date=timestamp,
                        success=True,
                        confirmations=0,
                        from_address=sender,
                        to_address=recipient,
                        value=value,
                        symbol=contract_info.get('symbol'),
                        memo=None,
                        tx_fee=BlockchainUtilsMixin.from_unit(meta.get('fee', 0), precision=cls.precision),
                        token=mint,
                    )
                )
            processed_mints.add(mint)

        return transfers

    @classmethod
    def parse_batch_block_txs_response(
            cls, block_txs_response: List[dict]
    ) -> List[TransferTx]:
        """
        Parses a batch of block transaction responses and extracts both native SOL and SPL token transfers.

        This version uses separate utility functions for processing native and token transfers.
        """
        transfers: List[TransferTx] = []
        if not cls.validator.validate_block_txs_response(block_txs_response):
            return transfers

        for block in block_txs_response:
            result = block.get('result', {})
            if not cls.validator.validate_block(block):
                continue
            parent_slot = result.get('parentSlot', 0)
            block_height = parent_slot + 1

            transactions = result.get('transactions', [])
            for tx in transactions:
                block_time = tx.get('blockTime')
                timestamp = parse_utc_timestamp(block_time)
                tx_hash = tx.get('transaction', {}).get('signatures', [])[0]

                if cls.validator.validate_block_transaction(tx):
                    # Handle native SOL transfers
                    sol_transfers = cls._parse_native_sol_transfers(
                        tx, block_height, timestamp, tx_hash
                    )
                    transfers.extend(sol_transfers)

                if cls.validator.validate_token_block_transaction(tx):
                    token_transfers = cls._parse_spl_token_transfers(
                        tx, block_height, timestamp, tx_hash
                    )
                    transfers.extend(token_transfers)

        return transfers

    @classmethod
    def parse_token_tx_details_response(cls, tx_details_response: dict, block_head: int) -> List[TransferTx]:
        """
            Parses token transaction details from the RPC response.

            Returns:
                List[TransferTx]: List of parsed token transfers
        """
        if not (cls.validator.validate_tx_details_response(tx_details_response)
                and cls.validator.validate_token_transaction(tx_details_response.get('result'))):
            return []

        result = tx_details_response.get('result', {})
        instructions = result.get('transaction', {}).get('message', {}).get('instructions', [])
        if not any(cls.validator.validate_instruction(ix) for ix in instructions):
            return []
        logs = result.get('meta', {}).get('logMessages', [])

        if not cls.validator.validate_logs(logs):
            return []

        transfers = []

        pre_token_balances = result.get('meta', {}).get('preTokenBalances', [])
        post_token_balances = result.get('meta', {}).get('postTokenBalances', [])

        if not pre_token_balances or not post_token_balances:
            return []

        pre_balances_map = {b.get('accountIndex'): b for b in pre_token_balances}
        post_balances_map = {b.get('accountIndex'): b for b in post_token_balances}

        senders = []
        for idx, pre_balance in pre_balances_map.items():
            mint = pre_balance.get('mint')
            pre_amount = int(pre_balance.get('uiTokenAmount', {}).get('amount', '0'))
            post_amount = 0

            if idx in post_balances_map:
                post_amount = int(post_balances_map[idx].get('uiTokenAmount', {}).get('amount', '0'))

            if pre_amount > post_amount:
                senders.append({
                    'index': idx,
                    'address': pre_balance.get('owner'),
                    'mint': mint,
                    'amount': pre_amount - post_amount,
                    'decimals': pre_balance.get('uiTokenAmount', {}).get('decimals', 0)
                })

        recipients = []
        for idx, post_balance in post_balances_map.items():
            mint = post_balance.get('mint')
            post_amount = int(post_balance.get('uiTokenAmount', {}).get('amount', '0'))
            pre_amount = 0

            if idx in pre_balances_map:
                pre_amount = int(pre_balances_map[idx].get('uiTokenAmount', {}).get('amount', '0'))

            if post_amount > pre_amount:
                recipients.append({
                    'index': idx,
                    'address': post_balance.get('owner'),
                    'mint': mint,
                    'amount': post_amount - pre_amount,
                    'decimals': post_balance.get('uiTokenAmount', {}).get('decimals', 0)
                })

        for sender in senders:
            mint = sender['mint']
            currency = cls.contract_currency_list().get(mint)
            if not currency:
                continue

            contract_info = cls.contract_info_list().get(currency)
            if not contract_info:
                continue
            matching_recipients = [r for r in recipients if r['mint'] == mint]

            for recipient in matching_recipients:
                if sender['address'] == recipient['address']:
                    continue

                value = BlockchainUtilsMixin.from_unit(
                    recipient['amount'], precision=contract_info.get('decimals')
                )

                transfers.append(
                    TransferTx(
                        block_height=result.get('slot'),
                        block_hash=None,
                        tx_hash=result.get('transaction', {}).get('signatures', [])[0],
                        date=parse_utc_timestamp(result.get('blockTime')),
                        success=True,
                        confirmations=block_head - result.get('slot'),
                        from_address=sender['address'],
                        to_address=recipient['address'],
                        value=value,
                        symbol=contract_info.get('symbol'),
                        memo=None,
                        tx_fee=BlockchainUtilsMixin.from_unit(
                            result.get('meta', {}).get('fee', 0), cls.precision
                        ),
                        token=mint,
                    )
                )

        return transfers

    @classmethod
    def parse_token_txs_response(
            cls,
            _: str,
            token_txs_response: list,
            block_head: int,
            contract_info: dict,
            __: str = '',
    ) -> List[TransferTx]:
        """
        Parses token transactions from Solana RPC responses.
        """
        if not cls.validator.validate_address_txs_response(token_txs_response):
            return []

        all_transfers = []
        processed_tx_signatures = set()

        for tx in token_txs_response:
            if not (
                    cls.validator.validate_tx_details_response(tx)
                    and cls.validator.validate_token_transaction(tx.get('result'))
            ):
                continue

            result = tx.get('result', {})
            instructions = result.get('transaction', {}).get('message', {}).get('instructions', [])
            if not any(cls.validator.validate_instruction(ix) for ix in instructions):
                continue
            logs = result.get('meta', {}).get('logMessages', [])

            if not cls.validator.validate_logs(logs):
                continue

            tx_signature = result.get('transaction', {}).get('signatures', [])[0]

            if tx_signature in processed_tx_signatures:
                continue

            pre_token_balances = result.get('meta', {}).get('preTokenBalances', [])
            post_token_balances = result.get('meta', {}).get('postTokenBalances', [])

            if not pre_token_balances or not post_token_balances:
                continue

            pre_balances_map = {b.get('accountIndex'): b for b in pre_token_balances}
            post_balances_map = {b.get('accountIndex'): b for b in post_token_balances}

            token_transfers = {}  # mint -> {senders: [], recipients: []}

            for idx, pre_balance in pre_balances_map.items():
                mint = pre_balance.get('mint')
                pre_amount = int(pre_balance.get('uiTokenAmount', {}).get('amount', '0'))
                post_amount = 0

                if idx in post_balances_map:
                    post_amount = int(
                        post_balances_map[idx].get('uiTokenAmount', {}).get('amount', '0')
                    )

                if pre_amount > post_amount:
                    if mint not in token_transfers:
                        token_transfers[mint] = {'senders': [], 'recipients': []}

                    token_transfers[mint]['senders'].append(
                        {
                            'address': pre_balance.get('owner'),
                            'amount': pre_amount - post_amount,
                            'decimals': pre_balance.get('uiTokenAmount', {}).get(
                                'decimals', 0
                            ),
                        }
                    )

            for idx, post_balance in post_balances_map.items():
                mint = post_balance.get('mint')
                post_amount = int(post_balance.get('uiTokenAmount', {}).get('amount', '0'))
                pre_amount = 0

                if idx in pre_balances_map:
                    pre_amount = int(
                        pre_balances_map[idx].get('uiTokenAmount', {}).get('amount', '0')
                    )

                if post_amount > pre_amount:
                    if mint not in token_transfers:
                        token_transfers[mint] = {'senders': [], 'recipients': []}

                    token_transfers[mint]['recipients'].append(
                        {
                            'address': post_balance.get('owner'),
                            'amount': post_amount - pre_amount,
                            'decimals': post_balance.get('uiTokenAmount', {}).get(
                                'decimals', 0
                            ),
                        }
                    )

            tx_transfers = []
            mint_contract = contract_info.get('address')

            if mint_contract in token_transfers:
                mint_data = token_transfers[mint_contract]
                currency = cls.contract_currency_list().get(mint_contract)

                if currency:
                    token_contract_info = cls.contract_info_list().get(currency)

                    if (
                            token_contract_info
                            and mint_data['senders']
                            and mint_data['recipients']
                    ):
                        sender = mint_data['senders'][0]
                        recipient = mint_data['recipients'][0]

                        if sender['address'] != recipient['address']:
                            value = BlockchainUtilsMixin.from_unit(
                                recipient['amount'], precision=contract_info.get('decimals')
                            )

                            tx_transfers.append(
                                TransferTx(
                                    block_height=result.get('slot'),
                                    block_hash=None,
                                    tx_hash=tx_signature,
                                    date=parse_utc_timestamp(result.get('blockTime')),
                                    success=True,
                                    confirmations=block_head - result.get('slot'),
                                    from_address=sender['address'],
                                    to_address=recipient['address'],
                                    value=value,
                                    symbol=token_contract_info.get('symbol'),
                                    memo=None,
                                    tx_fee=BlockchainUtilsMixin.from_unit(
                                        result.get('meta', {}).get('fee', 0), cls.precision
                                    ),
                                    token=mint_contract,
                                )
                            )

            all_transfers.extend(tx_transfers)
            processed_tx_signatures.add(tx_signature)

        return all_transfers


class RpcSolAPI(GeneralApi):
    parser = RpcSolParser
    symbol = 'SOL'
    cache_key = 'sol'
    rate_limit = 0.1
    get_txs_limit = 1
    max_block_in_single_request = 1
    block_height_offset = 120
    GET_BLOCK_ADDRESSES_MAX_NUM = 160
    GET_BALANCES_MAX_ADDRESS_NUM = 100
    SUPPORT_GET_BALANCE_BATCH = True
    SUPPORT_BATCH_GET_BLOCKS = True
    BALANCES_NOT_INCLUDE_ADDRESS = True
    supported_requests = {
        'get_balance': '',
        'get_balances': '',
        'get_block_head': '',
        'get_address_txs': '',
        'get_tx_details': '',
        'get_blocks_txs': '',
        'get_token_tx_details': '',
        'get_token_txs': '',
    }

    @classmethod
    def get_headers(cls) -> dict:
        return {'content-type': 'application/json'}

    @classmethod
    def get_balance_body(cls, address: str) -> str:
        data = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getBalance',
            'params': [address]
        }
        return json.dumps(data)

    @classmethod
    def get_balances_body(cls, addresses: List[str]) -> str:
        data = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getMultipleAccounts',
            'params': [addresses],
        }
        return json.dumps(data)

    @classmethod
    def get_block_head_body(cls) -> str:
        data = {
            'jsonrpc': '2.0',
            'id': 1,
            'method': 'getEpochInfo',
        }
        return json.dumps(data)

    @classmethod
    def get_txs_hash_body(cls, address: str) -> str:
        get_txs_hash_data = {
            'jsonrpc': '2.0',
            'id': 0,
            'method': 'getSignaturesForAddress',
            'params': [
                address,
                {'limit': cls.get_txs_limit, 'commitment': 'finalized'},
            ],
        }
        return json.dumps(get_txs_hash_data)

    @classmethod
    def get_address_txs_body(cls, txs_hash: str) -> str:
        batch_data = []
        index = 1
        for tx_hash in txs_hash:
            get_tx_detail_data = {
                'jsonrpc': '2.0',
                'id': index,
                'method': 'getTransaction',
                'params': [
                    tx_hash,
                    {
                        'encoding': 'jsonParsed',
                        'maxSupportedTransactionVersion': 0,
                    }
                ]
            }
            index += 1
            batch_data.append(get_tx_detail_data)
        return json.dumps(batch_data)

    @classmethod
    def get_tx_details_body(cls, tx_hash: str) -> str:
        data = {
            'jsonrpc': '2.0',
            'id': 0,
            'method': 'getTransaction',
            'params': [
                tx_hash,
                {
                    'encoding': 'jsonParsed',
                    'maxSupportedTransactionVersion': 0,
                },
            ],
        }
        return json.dumps(data)

    @classmethod
    def get_token_tx_details_body(cls, tx_hash: str) -> str:
        return cls.get_tx_details_body(tx_hash)

    @classmethod
    def get_txs_hash(cls, address: str) -> Any:
        return cls.request(request_method='', body=cls.get_txs_hash_body(address),
                           headers=cls.get_headers(), address=address)

    @classmethod
    def get_token_txs(cls, txs_hash: str, _: dict, __: str = '') -> Any:
        return cls.request(
            request_method='',
            body=cls.get_address_txs_body(txs_hash),
            headers=cls.get_headers(),
        )

    @classmethod
    def get_address_txs(cls, txs_hash: List[str], **kwargs: Any) -> Any:
        return cls.request(request_method='', body=cls.get_address_txs_body(txs_hash), headers=cls.get_headers())

    @classmethod
    def get_blocks_txs_body_auxiliary(cls, index: int, blocks_txs_response: dict) -> str:
        block_index = index * cls.max_block_in_single_request
        data = []
        for i in range(cls.max_block_in_single_request):
            data.append(
                {
                    'jsonrpc': '2.0',
                    'id': i + 3,
                    'method': 'getBlock',
                    'params': [
                        blocks_txs_response.get('result')[block_index],
                        {
                            'encoding': 'jsonParsed',
                            'transactionDetails': 'accounts',
                            'rewards': False,
                            'maxSupportedTransactionVersion': 0
                        }
                    ]
                }
            )
            block_index += 1
            if block_index >= len(blocks_txs_response.get('result')):
                break
        return json.dumps(data)

    @classmethod
    def get_blocks_txs_body(cls, from_block: int, to_block: int) -> str:
        data = {
            'jsonrpc': '2.0',
            'id': 2,
            'method': 'getBlocks',
            'params': [from_block, to_block],
        }
        return json.dumps(data)

    @classmethod
    def get_blocks_txs(cls, index: int, block_txs_response: dict) -> Any:
        return cls.request('', body=cls.get_blocks_txs_body_auxiliary(index, block_txs_response),
                           headers=cls.get_headers())


class SerumRPC(RpcSolAPI):
    _base_url = 'https://solana-api.projectserum.com'
    max_block_in_single_request = 9
    get_txs_limit = 25
    rate_limit = 0.1


class AnkrRPC(RpcSolAPI):  # We have to pay to use this API
    _base_url = 'https://rpc.ankr.com/solana/c70cf02cf0e7614419a8f19d4768f94525e1fdff20ffc15670c671ff3f9ed39f'
    max_block_in_single_request = 10
    get_txs_limit = 20
    rate_limit = 0.05
    USE_PROXY = bool(not settings.IS_VIP)


class QuickNodeRPC(RpcSolAPI):
    # the api key should only be available in production
    _base_url = 'https://powerful-summer-valley.solana-mainnet.quiknode.pro/0d3e1d76fe293d1c955c63c1eeb878d93f54602b'
    # settings.SOLANA_QUICK_NODE_URLS if not settings.IS_VIP else ''
    max_block_in_single_request = 60  # it can be more, but we won't increase it for decreasing pressure on explorer
    get_txs_limit = 20
    GET_BLOCK_ADDRESSES_MAX_NUM = 300
    max_workers_for_get_block = 10
    USE_PROXY = False


class AlchemyRPC(RpcSolAPI):
    _base_url = random.choice(settings.SOLANA_ALCHEMY_URLS) if not settings.IS_VIP else ''
    max_block_in_single_request = 7
    get_txs_limit = 35
    rate_limit = 0
    USE_PROXY = True


class ShadowRPC(RpcSolAPI):
    _base_url = 'https://ssc-dao.genesysgo.net/'
    max_block_in_single_request = 30
    get_txs_limit = 25
    rate_limit = 0.005


class MainRPC(RpcSolAPI):
    # alternatively use https://explorer-api.mainnet-beta.solana.com but usually it doesn't work
    _base_url = 'https://api.mainnet-beta.solana.com'
    max_block_in_single_request = 1
    get_txs_limit = 1
    rate_limit = 0.1
    USE_PROXY = True
