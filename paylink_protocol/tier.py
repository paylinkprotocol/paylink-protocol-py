from typing import TypeVar, Tuple, Dict
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

    def costs(self, _type: PurchaseType, cost: float | int, time: int | str = 0, burnPercentage: int = 0) -> 'TierOptionBuilder[T]':
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
        if burnPercentage not in self.options[_type]:
            self.options[_type][burnPercentage] = {}
        if time not in self.options[_type][burnPercentage]:
            self.options[_type][burnPercentage][time] = cost
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
            for burnPercentage in option.options[_type]:
                if burnPercentage not in self.options[_type]:
                    self.options[_type][burnPercentage] = {}
                for time in option.options[_type][burnPercentage]:
                    if time not in self.options[_type][burnPercentage]:
                        self.options[_type][burnPercentage][time] = {}
                    cost = option.options[_type][burnPercentage][time]
                    if cost in self.options[_type][burnPercentage][time]:
                        raise ValueError(
                            f'Cannot specify cost {cost} twice for type {_type}, time {time} and burn Percentage {burnPercentage}. Already specified tier: {self.options[_type][time][cost]}, trying to specify tier: {option.tier}')
                    self.options[_type][burnPercentage][time][cost] = option.tier

    def finish(self) -> Tuple[T, Dict[PurchaseType, Dict[int, Dict[float, T]]]]:
        if self.__default is None:
            raise ValueError('You have to specify a default Tier')
        return self.__default, self.options


class TierMapping[T]:
    def __init__(self, default, mapping, decimals, time_fuzz=60, cost_fuzz=500):
        self.default = default
        self.token_decimals = decimals
        self.time_fuzz = time_fuzz  # time fuzz, because transaction might take a while and is 'fuzzy', in seconds
        self.cost_fuzz = cost_fuzz  # cost fuzz, because of floating point precision with token decimals
        real_mapping = {}
        for _type in mapping:
            real_mapping[_type] = {}
            for burnPercentage in mapping[_type]:
                real_mapping[_type][burnPercentage] = {}
                for time in mapping[_type][burnPercentage]:
                    real_mapping[_type][burnPercentage][time] = {}
                    for cost in mapping[_type][burnPercentage][time]:
                        power = 18  # default ETH decimals
                        if _type in (PurchaseType.HOLDING, PurchaseType.PURCHASE_WITH_TOKENS):
                            power = decimals
                        real_cost = int(cost * (10**power))
                        real_mapping[_type][burnPercentage][time][real_cost] = mapping[_type][burnPercentage][time][cost]
        self.mapping = real_mapping

    def get_corresponding_tier(self, _type, time, burnPercentage, cost) -> T | None:
        if _type not in self.mapping:
            raise ValueError(f'Type {_type} is in active purchases, but not specified as a buyable option.')

        if burnPercentage not in self.mapping[_type]:
            raise ValueError(f'Incorrect burn percentage. You can fool noone')

        timings = list(self.mapping[_type][burnPercentage].keys())
        timings.sort()
        comparable_time = time - self.time_fuzz

        _time = timings[-1]

        for t in timings[::-1]:
            if comparable_time <= t:
                _time = t

        costs = list(self.mapping[_type][burnPercentage][_time].keys())
        costs.sort()

        amount_achieved = None

        comparable_cost = cost + self.cost_fuzz
        for c in costs:
            if comparable_cost >= c:
                amount_achieved = c

        if amount_achieved is None:
            if _type == PurchaseType.HOLDING:
                raise ValueError('Type is holding, but not enough for any tier')
            else:
                raise ValueError(f'User has made a purchase, but did not pay enough for lowest tier.')

        tier = self.mapping[_type][burnPercentage][_time][amount_achieved]

        return tier

