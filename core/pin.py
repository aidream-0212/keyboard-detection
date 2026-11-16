"""시험용 PIN 을 PBKDF2 해시로만 보관하고 확인한다. PIN 원문은 어디에도 저장하지 않는다."""

import hashlib
import hmac
import os

ITERATIONS = 200_000


def is_valid_pin(pin):
    """시험용 PIN 형식: 숫자 4~8자리."""
    return pin.isdigit() and 4 <= len(pin) <= 8


def hash_pin(pin):
    """PIN 을 해시로 바꾼다. 저장할 수 있는 dict(salt, hash)를 돌려준다."""
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, ITERATIONS)
    return {"salt": salt.hex(), "hash": digest.hex()}


def verify_pin(pin, stored):
    """입력한 PIN 이 저장된 해시와 맞는지 확인한다."""
    salt = bytes.fromhex(stored["salt"])
    digest = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, ITERATIONS)
    return hmac.compare_digest(digest.hex(), stored["hash"])
