import asyncio
import inspect
import time
from web3 import Web3, AsyncWeb3, WebSocketProvider
from eth_abi.abi import decode
from typing import Callable, Awaitable, Dict, Any, List, Generic, TypeVar, Tuple

from paylink_protocol.model import *
from paylink_protocol.resources import _min_block_id, defaultWebsocket, defaultRpc, routerAddress, purchaseTopicHash, \
    payLinkUrl
from paylink_protocol.util import create_encryption_key, encodePayLinkData, encryptUserId, decryptUserId
import logging
import traceback
from cachetools import TTLCache

logger = logging.getLogger(__name__)

TIMING_FUZZ = 0.95


# ToDo Purchase Manager Builder
class PurchaseManagerBuilder:
    def __init__(self, appId: int):
        self.appId = appId
        self.encryptionKey = create_encryption_key(appId)
        self.callback = None
        self.cache_time_seconds = None
        self.cache_size_items = None

    def with_callback(self,
                      purchase_callback: Callable[[PurchaseItem], Awaitable[None] | None]) -> 'PurchaseManagerBuilder':
        self.callback = purchase_callback
        return self

    def with_cache(self, cache_time_seconds: int = 600, cache_size_items: int = 300) -> 'PurchaseManagerBuilder':
        self.cache_time_seconds = cache_time_seconds
        self.cache_size_items = cache_size_items
        return self


T = TypeVar('T', bound=Enum)


class PurchaseManager[T]:

    def __init__(self, appId: int, secret: str, purchase_callback: Callable[[PurchaseItem], Awaitable[None] | None], tier_mapping: Tuple[T, Dict[PurchaseType, Dict[int, Dict[float, T]]]],
                 token_address: str, token_abi, websocketUrl: str = defaultWebsocket, rpcUrl: str = defaultRpc,
                 debug: bool = False, cache_time_seconds: int = 1200, cache_size_items: int = 300):
        self.appId = appId
        self.default_tier = tier_mapping[0]
        self.tier_mapping = tier_mapping[1]
        self.callback = purchase_callback
        self.encryptionKey = create_encryption_key(secret)
        self.websocketUrl = websocketUrl
        self.rpcUrl = rpcUrl
        self.debug = debug
        self.contract_address = Web3.to_checksum_address(routerAddress)
        self.topic_hash = purchaseTopicHash
        self.running = False
        self.stop_event = asyncio.Event()
        self.hold_cache = TTLCache(maxsize=cache_size_items, ttl=cache_time_seconds)
        self.active_purchases = {}
        self.token_address = token_address
        self.token_abi = token_abi
        self.token_contract = self.getTokenContract()
        self.token_decimals = self.token_contract.functions.decimals().call()

    def getTokenContract(self):
        return Web3(Web3.HTTPProvider(self.rpcUrl)).eth.contract(address=self.token_address, abi=self.token_abi)

    def initialize(self):
        self.active_purchases = {}
        to_delete = []
        used_holding_addresses = {}
        for p in self.getAllPurchases():
            if p.purchaseType == PurchaseType.HOLDING:
                if p.userWalletAddress in used_holding_addresses:
                    to_delete.append(used_holding_addresses[p.userWalletAddress])
                used_holding_addresses[p.userWalletAddress] = p
            if p.userId in self.active_purchases:
                self.active_purchases[p.userId].append(p)
            else:
                self.active_purchases[p.userId] = [p]
        for p in to_delete:
            self.active_purchases[p.userId].remove(p)
            if len(self.active_purchases[p.userId]) == 0:
                del self.active_purchases[p.userId]

    def getHoldAmount(self, purchase: PurchaseItem) -> float:
        amount = self.hold_cache.get(purchase.userWalletAddress, None)
        if amount is None:
            amount = self.getCurrentWalletHolding(purchase)
            logger.info(f'{purchase.purchaseTokenAddress} is holding: {amount}')
        return amount

    def getTimestampOfPurchase(self, purchase: PurchaseItem):
        web3 = Web3(Web3.HTTPProvider(self.rpcUrl))
        return web3.eth.get_block(purchase.blockNumber)['timestamp']

    def getTierOfPurchase(self, purchase: PurchaseItem) -> T | None:
        if purchase.tier is not None:
            return purchase.tier
        purchaseType = purchase.purchaseType
        runTime = 0
        if purchaseType != PurchaseType.HOLDING:
            runTime = purchase.expirationTimestamp - self.getTimestampOfPurchase(purchase)

        amount = purchase.purchaseAmount

        if purchaseType == PurchaseType.PURCHASE_WITH_TOKENS:
            amount = amount / (10**self.token_decimals)
        elif purchaseType == PurchaseType.PURCHASE_WITH_ETH:
            amount = amount / (10 ** 18)
        elif purchaseType == PurchaseType.HOLDING:
            amount = self.getHoldAmount(purchase)

        if purchaseType not in self.tier_mapping:
            logger.warning(
                f'Type {purchaseType} is in active purchases, but not specified as a buyable option. Purchase: {purchase}')
            return None

        timings = list(self.tier_mapping[purchaseType].keys())
        timings.sort()
        comparable_time = runTime * TIMING_FUZZ

        _time = timings[-1]

        for t in timings[::-1]:
            if comparable_time <= t:
                _time = t

        costs = list(self.tier_mapping[purchaseType][_time].keys())
        costs.sort()

        amount_achieved = None

        for c in costs:
            if amount >= c:
                amount_achieved = c

        if amount_achieved is None:
            if purchaseType == PurchaseType.HOLDING:
                logger.info(f'User is not holding enough for lowest holding tier')
            else:
                logger.critical(
                    f'User has made a purchase, but did not pay enough for lowest tier. Purchase: {purchase}')
            return None

        tier = self.tier_mapping[purchaseType][_time][amount_achieved]
        purchase.tier = tier
        return tier

    def getTiersForUser(self, userId: int) -> List[T]:
        tiers = [self.default_tier]
        # check existing purchases
        if userId in self.active_purchases:
            expired = []
            for purchase in self.active_purchases[userId]:
                if self.isPurchaseValid(purchase):
                    tier = self.getTierOfPurchase(purchase)
                    tiers.append(tier)
                else:
                    expired.append(purchase)
            for purchase in expired:
                self.active_purchases[userId].remove(purchase)
                if len(self.active_purchases[userId]) == 0:
                    del self.active_purchases[userId]
        return tiers

    def getCurrentWalletHolding(self, purchase: PurchaseItem) -> float:
        balance = self.token_contract.functions.balanceOf(Web3.to_checksum_address(purchase.userWalletAddress)).call()
        return balance / (10 ** self.token_decimals)

    def stop(self):
        self.stop_event.set()

    async def run_until_disconnect(self):
        self.initialize()
        self.running = True
        while not self.stop_event.is_set():
            try:
                async with AsyncWeb3(WebSocketProvider(self.websocketUrl)) as web3:
                    filter_params = {
                        "address": self.contract_address,
                        "topics": [
                            self.topic_hash,
                            "0x" + hex(self.appId).lower().replace("0x", "").rjust(64, "0"),
                        ],
                    }
                    subscription_id = await web3.eth.subscribe("logs", filter_params)

                    async for payload in web3.socket.process_subscriptions():
                        if "result" not in payload:
                            continue
                        item = self.__decodePurchase(payload["result"])
                        if item.userId in self.active_purchases:
                            self.active_purchases[item.userId].append(item)
                        else:
                            self.active_purchases[item.userId] = [item]
                        c = self.callback(item)
                        if inspect.isawaitable(c):
                            await c

            except Exception as e:
                logger.warning(f"Exception while processing purchase events: {e} {traceback.format_exc()}")
                await asyncio.sleep(5)
        self.running = False

    def createPayLink(self, userId: int):
        encryptedUserId = encryptUserId(userId, self.encryptionKey)
        print('encid', encryptedUserId)
        return payLinkUrl.format(data=encodePayLinkData(self.appId, encryptedUserId))

    def isPurchaseValid(self, purchase: PurchaseItem) -> bool:
        if purchase.purchaseType != PurchaseType.HOLDING:
            current_time = int(time.time())
            result = current_time < purchase.expirationTimestamp
            if not result:
                print(f'Purchase is expired: now:{current_time} expiration: {purchase.expirationTimestamp}')
            return result
        return True

    def getAllPurchases(self, includeExpiredPurchases: bool = False) -> List[PurchaseItem]:
        return self.__getPurchases([
            self.topic_hash,
            "0x" + hex(self.appId).lower().replace("0x", "").rjust(64, "0"),
            None,
            None
        ], includeExpiredPurchases)

    def getPurchasesByUserId(self, userId: int, includeExpiredPurchases: bool = False) -> List[PurchaseItem]:
        userId = encryptUserId(userId, self.encryptionKey)
        return self.__getPurchases([
            self.topic_hash,
            "0x" + hex(self.appId).lower().replace("0x", "").rjust(64, "0"),
            "0x" + hex(userId).lower().replace("0x", "").rjust(64, "0"),
            None
        ], includeExpiredPurchases)

    def getPurchasesByUserWalletAddress(self, userWalletAddress: str, includeExpiredPurchases: bool = False) -> \
            List[PurchaseItem]:
        return self.__getPurchases([
            self.topic_hash,
            "0x" + hex(self.appId).lower().replace("0x", "").rjust(64, "0"),
            None,
            "0x" + userWalletAddress.lower().replace("0x", "").rjust(64, "0")
        ], includeExpiredPurchases)

    def __getLatestBlockId(self):
        block = Web3(Web3.HTTPProvider(self.rpcUrl)).eth.get_block('latest')
        return block['number']

    def __getPurchases(self, topics: list, includeExpiredPurchases: bool) -> List[PurchaseItem]:
        block_id = self.__getLatestBlockId()
        min_block_id = _min_block_id

        purchases = []

        while min_block_id < block_id:

            filter_params = {
                "address": self.contract_address,
                "topics": topics,
                "fromBlock": min_block_id,
                "toBlock": min(min_block_id + 25000, block_id),
            }
            min_block_id = min(min_block_id + 25000, block_id) + 1
            logs = Web3(Web3.HTTPProvider(self.rpcUrl)).eth.get_logs(filter_params)
            print(f'got logs {min_block_id}, {block_id}', flush=True)
            for payload in logs:
                try:
                    item = self.__decodePurchase(payload)
                except:
                    print(f'error in decode: {traceback.format_exc()}')
                    continue
                logger.info(str(item))
                if includeExpiredPurchases:
                    purchases.append(item)
                elif self.isPurchaseValid(item):
                    purchases.append(item)
        print('Done')
        return purchases

    def __decodePurchase(self, result: Dict[str, Any]) -> PurchaseItem:
        txHash = "0x" + result["transactionHash"].hex()
        blockNumber = result["blockNumber"]

        topics = result["topics"]
        appId = int.from_bytes(topics[1], "big")
        userId = decryptUserId(int.from_bytes(topics[2], "big"), self.encryptionKey)
        userWalletAddress = decode(["address"], topics[3])[0]

        data = bytes(result["data"])
        decodedData = decode(["uint256", "address", "uint256", "uint256"], data)
        purchaseType = decodedData[0]
        purchaseTokenAddress = decodedData[1]
        purchaseAmount = decodedData[2]
        expirationTimestamp = decodedData[3]

        return PurchaseItem(
            txHash=txHash,
            blockNumber=blockNumber,
            appId=appId,
            userId=userId,
            userWalletAddress=userWalletAddress,
            purchaseType=PurchaseType(purchaseType),
            purchaseTokenAddress=purchaseTokenAddress,
            purchaseAmount=purchaseAmount,
            expirationTimestamp=expirationTimestamp
        )
