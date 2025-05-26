from typing import TypeVar, Generic, List, Tuple, Dict
from enum import Enum

from paylink_protocol.model import PurchaseType

T = TypeVar('T', bound=Enum)


YEAR = 60 * 60 * 24 * 365
MONTH = 60 * 60 * 24 * 30
WEEK = 60 * 60 * 24 * 7
DAY = 60 * 60 * 24


class TierOptionBuilder[T]:
    def __init__(self, tier: T, builder: 'TierBuilder[T]'):
        self.tier = tier
        self.options = {}
        self.builder = builder

    def newOption(self, tier: T) -> 'TierOptionBuilder[T]':
        return self.finish().newOption(tier)

    def costs(self, _type: PurchaseType, cost: float, time: int | str = 0) -> 'TierOptionBuilder[T]':
        orig_time = time
        if _type != PurchaseType.HOLDING and time == 0:
            raise ValueError('A non HOLD package needs to have a time specified')
        if _type == PurchaseType.HOLDING and time != 0:
            raise ValueError('A HOLD package cannot have a time specified')
        if cost == 0.0:
            raise ValueError(f'A cost of 0 cannot be specified for {self.tier}{_type}, use a default tier instead')
        if isinstance(time, str):
            time = time.lower()
            if time.isnumeric():
                time = int(time)
            else:
                match time[-1]:
                    case 'd':
                        time = int(time[:-1]) * DAY
                    case 'w':
                        time = int(time[:-1]) * WEEK
                    case 'm':
                        time = int(time[:-1]) * MONTH

        if _type not in self.options:
            self.options[_type] = {}
        if time not in self.options[_type]:
            self.options[_type][time] = cost
        else:
            raise ValueError(
                f'PurchaseType {_type} - Timeframe {orig_time} combination specified twice for {self.tier}')
        return self

    def default(self, tier: T) -> 'TierBuilder':
        return self.finish().default(tier)

    def build(self):
        return self.finish().finish()

    def finish(self):
        self.builder.constructOption(self)
        return self.builder


class TierBuilder[T]:
    def __init__(self):
        self.__default = None
        self.options = {}

    def default(self, tier: T) -> 'TierBuilder[T]':
        self.__default = tier
        return self

    def newOption(self, tier: T) -> TierOptionBuilder[T]:
        return TierOptionBuilder(tier, self)

    def constructOption(self, option: TierOptionBuilder[T]):
        if option.tier in self.options:
            raise ValueError(f'Tier {option.tier} specified twice')
        for _type in option.options:
            if _type not in self.options:
                self.options[_type] = {}
            for time in option.options[_type]:
                if time not in self.options[_type]:
                    self.options[_type][time] = {}
                cost = option.options[_type][time]
                if cost in self.options[_type][time]:
                    raise ValueError(
                        f'Cannot specify cost {cost} twice for type {_type} and time {time}. Already specified tier: {self.options[_type][time][cost]}, trying to specify tier: {option.tier}')
                self.options[_type][time][cost] = option.tier

    def finish(self) -> Tuple[T, Dict[PurchaseType, Dict[int, Dict[float, T]]]]:
        if self.__default is None:
            raise ValueError('You have to specify a default Tier')
        return self.__default, self.options

