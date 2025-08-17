# auth.py
from passlib.hash import bcrypt

def hash_password(plain: str) -> str:
    return bcrypt.hash(plain)  # incluye salt y factor de costo por defecto

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.verify(plain, hashed)
