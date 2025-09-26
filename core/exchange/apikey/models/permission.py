from __future__ import annotations

import enum


class Permission(enum.IntFlag):
    NONE = 0
    READ = enum.auto()
    TRADE = enum.auto()
    WITHDRAW = enum.auto()

    @classmethod
    def parse(cls, flags: str) -> Permission:
        result = Permission.NONE
        for f in flags.split(','):
            result |= Permission[f.strip()]
        return result

    def __str__(self) -> str:
        if self is Permission.NONE:
            return ''
        return ','.join([f.name for f in Permission if f.name is not None and f in self and f.value != 0])
