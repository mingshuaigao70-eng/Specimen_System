import scrypt
import os
import binascii
import secrets

def generate_scrypt_hash(password, salt=None):
    if salt is None:
        salt_bytes = os.urandom(16)
    else:
        salt_bytes = salt
    salt_hex = binascii.hexlify(salt_bytes).decode()
    hash_val = scrypt.hash(password.encode(), salt_bytes, N=32768, r=8, p=1)
    return f"scrypt32768:8:1${salt_hex}${binascii.hexlify(hash_val).decode()}"

def check_scrypt_hash(stored_hash, input_password):
    try:
        parts = stored_hash.split('$')
        salt = binascii.unhexlify(parts[1])
        stored_key = parts[2]
        new_hash = scrypt.hash(input_password.encode(), salt, N=32768, r=8, p=1)
        return secrets.compare_digest(stored_key, binascii.hexlify(new_hash).decode())
    except:
        return False