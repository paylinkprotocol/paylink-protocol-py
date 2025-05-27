from Crypto.Hash import SHA256


testnet_min_block_id = 8309015
mainent_min_block_id = 22540453

defaultWebsocketMainnet = "wss://ethereum-rpc.publicnode.com"
defaultWebsocketTestnet = "wss://ethereum-sepolia-rpc.publicnode.com"

defaultRpcMainnet = "https://rpc.flashbots.net/fast"
defaultRpcTestnet = "https://0xrpc.io/sep"

routerAddressMainnet = "0x4DFa81eB3c2215420d25EAeB72513ed63D9Ce9D9"
routerAddressTestnet = "0x8e722D3F88F9ceb5bf5cda22E2a7a6A9068d72E3"

weth_testnet = '0x7b79995e5f793A07Bc00c21412e50Ecae098E7f9'
weth_mainnet = '0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2'

purchaseTopicHash = "0xd925127addef674066ef51b2139e736e60b51254deea2faa5d4c606e1a91ac17"

payLinkUrl = "https://www.paylink.xyz/?{data}"

# Encryption
_PBKDF_salt = bytes.fromhex('31c87b40eb891d0a8f4337c08b3634d7')
_PBKDF_count = 100000
_PBKDF_hmac_hash = SHA256
