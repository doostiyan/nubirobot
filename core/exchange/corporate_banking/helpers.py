from typing import Optional

from exchange.corporate_banking.models import NOBITEX_BANK_CHOICES, TOMAN_BANKS


def get_nobitex_bank_choice_from_jibit_name(jibit_bank: str) -> Optional[int]:
    """
    Given a string from JIBIT_BANKS, return the corresponding NOBITEX_BANK_CHOICES choice.
    If none matches, return None.
    """
    if jibit_bank == 'MARKAZI':
        return NOBITEX_BANK_CHOICES.centralbank
    if jibit_bank == 'SANAT_VA_MADAN':
        return NOBITEX_BANK_CHOICES.sanatomadan
    if jibit_bank == 'MELLAT':
        return NOBITEX_BANK_CHOICES.mellat
    if jibit_bank == 'REFAH':
        return NOBITEX_BANK_CHOICES.refah
    if jibit_bank == 'MASKAN':
        return NOBITEX_BANK_CHOICES.maskan
    if jibit_bank == 'SEPAH':
        return NOBITEX_BANK_CHOICES.sepah
    if jibit_bank == 'KESHAVARZI':
        return NOBITEX_BANK_CHOICES.keshavarzi
    if jibit_bank == 'MELI':
        return NOBITEX_BANK_CHOICES.melli
    if jibit_bank == 'TEJARAT':
        return NOBITEX_BANK_CHOICES.tejarat
    if jibit_bank == 'SADERAT':
        return NOBITEX_BANK_CHOICES.saderat
    if jibit_bank == 'TOSEAH_SADERAT':
        return NOBITEX_BANK_CHOICES.toseesaderat
    if jibit_bank == 'POST':
        return NOBITEX_BANK_CHOICES.postbank
    if jibit_bank == 'TOSEAH_TAAVON':
        return NOBITEX_BANK_CHOICES.toseetaavon
    if jibit_bank == 'TOSEAH':
        return NOBITEX_BANK_CHOICES.tosee
    if jibit_bank == 'GHAVAMIN':
        return NOBITEX_BANK_CHOICES.ghavamin
    if jibit_bank == 'KARAFARIN':
        return NOBITEX_BANK_CHOICES.karafarin
    if jibit_bank == 'PARSIAN':
        return NOBITEX_BANK_CHOICES.parsian
    if jibit_bank == 'EGHTESADE_NOVIN':
        return NOBITEX_BANK_CHOICES.eghtesadenovin
    if jibit_bank == 'SAMAN':
        return NOBITEX_BANK_CHOICES.saman
    if jibit_bank == 'PASARGAD':
        return NOBITEX_BANK_CHOICES.pasargad
    if jibit_bank == 'SARMAIEH':
        return NOBITEX_BANK_CHOICES.sarmayeh
    if jibit_bank == 'SINA':
        return NOBITEX_BANK_CHOICES.sina
    if jibit_bank == 'MEHR_IRANIAN':
        return NOBITEX_BANK_CHOICES.mehreiran
    if jibit_bank == 'SHAHR':
        return NOBITEX_BANK_CHOICES.shahr
    if jibit_bank == 'AYANDEH':
        return NOBITEX_BANK_CHOICES.ayandeh
    if jibit_bank == 'ANSAR':
        return NOBITEX_BANK_CHOICES.ansar
    if jibit_bank == 'GARDESHGARI':
        return NOBITEX_BANK_CHOICES.gardeshgari
    if jibit_bank == 'HEKMAT_IRANIAN':
        return NOBITEX_BANK_CHOICES.hekmateiraninan
    if jibit_bank == 'DEY':
        return NOBITEX_BANK_CHOICES.dey
    if jibit_bank == 'IRANZAMIN':
        return NOBITEX_BANK_CHOICES.iranzamin
    if jibit_bank == 'RESALAT':
        return NOBITEX_BANK_CHOICES.resalat
    if jibit_bank == 'KOSAR':
        return NOBITEX_BANK_CHOICES.kowsar
    if jibit_bank == 'MELAL':
        return NOBITEX_BANK_CHOICES.melal
    if jibit_bank == 'KAVARMIANEH':
        return NOBITEX_BANK_CHOICES.khavarmiane
    if jibit_bank == 'NOOR':
        return NOBITEX_BANK_CHOICES.noor

    return None


def get_nobitex_bank_choice_from_toman_choice(toman_bank: int) -> Optional[int]:
    """
    Given the Python value from TOMAN_BANKS (e.g. 'Shahr'),
    return the corresponding NOBITEX_BANK_CHOICES choice (e.g. NOBITEX_BANK_CHOICES.shahr => code=61).
    If none matches, return None.
    """
    if toman_bank == TOMAN_BANKS.Shahr:
        return NOBITEX_BANK_CHOICES.shahr
    if toman_bank == TOMAN_BANKS.Melli:
        return NOBITEX_BANK_CHOICES.melli
    if toman_bank == TOMAN_BANKS.Mellat:
        return NOBITEX_BANK_CHOICES.mellat
    if toman_bank == TOMAN_BANKS.Tejarat:
        return NOBITEX_BANK_CHOICES.tejarat
    if toman_bank == TOMAN_BANKS.Keshavarzi:
        return NOBITEX_BANK_CHOICES.keshavarzi
    if toman_bank == TOMAN_BANKS.RefahKargaran:
        return NOBITEX_BANK_CHOICES.refah
    if toman_bank == TOMAN_BANKS.Pasargad:
        return NOBITEX_BANK_CHOICES.pasargad
    if toman_bank == TOMAN_BANKS.Sepah:
        return NOBITEX_BANK_CHOICES.sepah
    if toman_bank == TOMAN_BANKS.Saderat:
        return NOBITEX_BANK_CHOICES.saderat
    if toman_bank == TOMAN_BANKS.Resalat:
        return NOBITEX_BANK_CHOICES.resalat
    if toman_bank == TOMAN_BANKS.Ayande:
        return NOBITEX_BANK_CHOICES.ayandeh
    if toman_bank == TOMAN_BANKS.Maskan:
        return NOBITEX_BANK_CHOICES.maskan
    if toman_bank == TOMAN_BANKS.Saman:
        return NOBITEX_BANK_CHOICES.saman
    if toman_bank == TOMAN_BANKS.Parsian:
        return NOBITEX_BANK_CHOICES.parsian

    return None
