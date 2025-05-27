from dataclasses import dataclass
from enum import Enum
from typing import Any


class PurchaseType(Enum):
    HOLDING = 0
    PURCHASE_WITH_ETH = 1
    PURCHASE_WITH_TOKENS = 2


@dataclass
class PurchaseItem:
    txHash: str
    blockNumber: int
    appId: int
    userId: int
    userWalletAddress: str
    purchaseType: PurchaseType
    purchaseTokenAddress: str
    purchaseAmount: int
    expirationTimestamp: int
    burnPercentage: int
    clientWalletAddress: str
    tier: Any = None
