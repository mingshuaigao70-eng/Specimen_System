import hashlib
import os
# 生成密码hash
def generate_scrypt_hash(password):

    salt = os.urandom(16)

    key = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=16384,
        r=8,
        p=1
    )

    return salt.hex() + ":" + key.hex()


# 验证密码
def verify_scrypt_hash(password, stored_hash):

    salt_hex, key_hex = stored_hash.split(":")

    salt = bytes.fromhex(salt_hex)

    new_key = hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=16384,
        r=8,
        p=1
    )

    return new_key.hex() == key_hex