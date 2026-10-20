"""16-round TEA with QQ padding and chaining; no Java dependency."""
import secrets
import struct
from .errors import GFontError

GFONT_KEY = bytes.fromhex("01 09 08 09 00 08 02 06 01 09 09 02 00 08 02 08")
MASK = 0xFFFFFFFF
DELTA = 0x9E3779B9


def _xor(a, b):
    return bytes(x ^ y for x, y in zip(a, b))


def _block(data, key, decrypt=False):
    y, z = struct.unpack(">2I", data)
    a, b, c, d = struct.unpack(">4I", key)
    total = (DELTA * 16) & MASK if decrypt else 0
    for _ in range(16):
        if decrypt:
            z = (z - (((y << 4) + c) ^ (y + total) ^ ((y >> 5) + d))) & MASK
            y = (y - (((z << 4) + a) ^ (z + total) ^ ((z >> 5) + b))) & MASK
            total = (total - DELTA) & MASK
        else:
            total = (total + DELTA) & MASK
            y = (y + (((z << 4) + a) ^ (z + total) ^ ((z >> 5) + b))) & MASK
            z = (z + (((y << 4) + c) ^ (y + total) ^ ((y >> 5) + d))) & MASK
    return struct.pack(">2I", y, z)


class QQTea:
    @staticmethod
    def encrypt(data: bytes, key: bytes = GFONT_KEY) -> bytes:
        if len(key) != 16:
            raise GFontError("QQTea key must be 16 bytes")
        pad = (-(len(data) + 10)) % 8
        plain = bytes([(secrets.randbits(8) & 0xF8) | pad]) + secrets.token_bytes(pad + 2) + data + bytes(7)
        previous_cipher = previous_mixed = bytes(8)
        result = []
        for offset in range(0, len(plain), 8):
            mixed = _xor(plain[offset:offset + 8], previous_cipher)
            cipher = _xor(_block(mixed, key), previous_mixed)
            result.append(cipher)
            previous_cipher, previous_mixed = cipher, mixed
        return b"".join(result)

    @staticmethod
    def decrypt(data: bytes, key: bytes = GFONT_KEY) -> bytes:
        if len(key) != 16 or len(data) < 16 or len(data) % 8:
            raise GFontError("Invalid QQTea key or ciphertext length")
        previous_cipher = previous_mixed = bytes(8)
        result = []
        for offset in range(0, len(data), 8):
            cipher = data[offset:offset + 8]
            mixed = _block(_xor(cipher, previous_mixed), key, True)
            result.append(_xor(mixed, previous_cipher))
            previous_cipher, previous_mixed = cipher, mixed
        plain = b"".join(result)
        start = 1 + (plain[0] & 7) + 2
        if start > len(plain) - 7 or plain[-7:] != bytes(7):
            raise GFontError("Invalid QQTea padding or key")
        return plain[start:-7]
