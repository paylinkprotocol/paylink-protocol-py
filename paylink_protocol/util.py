from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Util.number import long_to_bytes, bytes_to_long
from paylink_protocol.resources import _PBKDF_salt, _PBKDF_count, _PBKDF_hmac_hash
from Crypto.Util.Padding import pad, unpad


def encodePayLinkData(appId: int, userId: int = 0) -> str:
    def to_b36(n: int) -> str:
        return ''.join("0123456789abcdefghijklmnopqrstuvwxyz"[r] for r in _divmod36(n)) or "0"

    def _divmod36(n: int):
        if n == 0: return [0]
        digits = []
        while n:
            n, r = divmod(n, 36)
            digits.insert(0, r)
        return digits

    a = to_b36(appId)
    u = to_b36(userId)
    l = f"{len(a):02}"
    return l + a + u


def encryptUserId(value: int, key: int) -> int:
    key = long_to_bytes(key)
    cipher = AES.new(key, AES.MODE_ECB)
    ciphertext = cipher.encrypt(pad(long_to_bytes(value), 16))
    return bytes_to_long(ciphertext)


def int_to_padded_bytes(n: int, block_size: int = 16) -> bytes:
    final_size = block_size
    while final_size < (n.bit_length() + 7) // 8:
        final_size += 16
    byte_data = n.to_bytes(final_size, byteorder='big')
    return byte_data


def decryptUserId(encrypted: int, key: int) -> int:
    key = long_to_bytes(key)
    cipher = AES.new(key, AES.MODE_ECB)
    plaintext = unpad(cipher.decrypt(int_to_padded_bytes(encrypted, 16)), 16)
    return bytes_to_long(plaintext)


def create_encryption_key(secret: int | str):
    if isinstance(secret, str):
        password = secret.encode()
    else:
        password = long_to_bytes(secret)
    keys = PBKDF2(password, _PBKDF_salt, count=_PBKDF_count, hmac_hash_module=_PBKDF_hmac_hash)
    return bytes_to_long(keys[:32])
