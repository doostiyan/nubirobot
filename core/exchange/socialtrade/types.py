from typing import Dict

from exchange.socialtrade.enums import WinratePeriods

WinrateDict = Dict[WinratePeriods, int]
WinratesDict = Dict[int, WinrateDict]
