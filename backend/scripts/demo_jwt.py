"""Learning demo: create a JWT, look inside it, then try to cheat it.

Run from backend/:  uv run python -m scripts.demo_jwt
Uses its own demo secret, so it doesn't need .env.
"""

import base64
import json
import time

import jwt

# In the real app this is JWT_SECRET_KEY from .env. Must be >= 32 bytes, or PyJWT warns
# that it's short enough to brute-force.
SECRET = "reception-stamp-demo-secret-0123456789"


def step(msg: str) -> None:
    print(f"\n===== {msg} =====")


def peek(part: str) -> dict:
    # A JWT part is just base64url-encoded JSON: no key needed to read it.
    return json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))


def b64(data: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


step("1. Login succeeded: server creates a token for user 2")
token = jwt.encode({"sub": "2", "exp": int(time.time()) + 1800}, SECRET, algorithm="HS256")
print(token)

step("2. The token is 3 parts separated by dots")
header, payload, signature = token.split(".")
print("header   :", header)
print("payload  :", payload)
print("signature:", signature)

step("3. Anyone can READ the first two parts (no secret needed)")
print("header  ->", peek(header))
print("payload ->", peek(payload))

step("4. Server verifies it with the secret: OK")
print(jwt.decode(token, SECRET, algorithms=["HS256"]))

step("5. Cheat #1: change sub from '2' to '1' (pretend to be another user)")
forged = f"{header}.{b64({'sub': '1', 'exp': peek(payload)['exp']})}.{signature}"
try:
    jwt.decode(forged, SECRET, algorithms=["HS256"])
except jwt.InvalidSignatureError as e:
    print("REJECTED:", e, "-> the stamp doesn't match the changed contents")

step("6. Cheat #2: make a brand-new token with a guessed secret")
fake = jwt.encode({"sub": "1", "exp": int(time.time()) + 1800}, "attacker-guessed-secret-0123456789", algorithm="HS256")
try:
    jwt.decode(fake, SECRET, algorithms=["HS256"])
except jwt.InvalidSignatureError as e:
    print("REJECTED:", e, "-> wrong stamp machine")

step("7. Cheat #3: reuse an old token after it expired")
old = jwt.encode({"sub": "2", "exp": int(time.time()) - 60}, SECRET, algorithm="HS256")
try:
    jwt.decode(old, SECRET, algorithms=["HS256"])
except jwt.ExpiredSignatureError as e:
    print("REJECTED:", e, "-> badge expired, log in again")
