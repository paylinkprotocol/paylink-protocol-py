from Crypto.Hash import SHA256

_testnetMode = True

_min_block_id = 22540453 if not _testnetMode else 8309015

_defaultWebsocketMainnet = "wss://ethereum-rpc.publicnode.com"
_defaultWebsocketTestnet = "wss://ethereum-sepolia-rpc.publicnode.com"
defaultWebsocket = _defaultWebsocketTestnet if _testnetMode else _defaultWebsocketMainnet

_defaultRpcMainnet = "https://rpc.flashbots.net/fast"
_defaultRpcTestnet = "https://0xrpc.io/sep"
defaultRpc = _defaultRpcTestnet if _testnetMode else _defaultRpcMainnet

_routerAddressMainnet = "0xFcFB187EF444D7b01253BB4FAF862C32b36E5aB8"
_routerAddressTestnet = "0xFcFB187EF444D7b01253BB4FAF862C32b36E5aB8"
routerAddress = _routerAddressTestnet if _testnetMode else _routerAddressMainnet

purchaseTopicHash = "0x4d4815c24dfeda514133b69dffd62369b1e91593b208a9eb14c11e9e6979fb4b"

payLinkUrl = "https://www.paylink.xyz/{data}"

# Encryption
_PBKDF_salt = bytes.fromhex('31c87b40eb891d0a8f4337c08b3634d7')
_PBKDF_count = 100000
_PBKDF_hmac_hash = SHA256
