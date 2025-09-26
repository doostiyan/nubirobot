from typing import Dict, Tuple

from exchange.integrations.types import CardToIbanAPICallResultV2, IdentityVerificationClientResult


class VerificationClientBase:
    name: str

    def request(self, url: str, data: Dict) -> Dict:
        raise NotImplementedError()

    def get_token(self) -> str:
        raise NotImplementedError()

    def get_user_identity(self, user) -> IdentityVerificationClientResult:
        raise NotImplementedError()

    def is_national_code_owner_of_mobile_number(self, national_code: str, mobile: str) -> Tuple[bool, dict]:
        raise NotImplementedError()

    def is_user_owner_of_iban(self, first_name: str, last_name: str, iban: str) -> Tuple[bool, dict]:
        raise NotImplementedError()

    def is_user_owner_of_bank_card(self, full_name: str, card_number: str) -> Tuple[bool, dict]:
        raise NotImplementedError()

    def convert_card_number_to_iban(self, card_number: str) -> CardToIbanAPICallResultV2:
        raise NotImplementedError()
