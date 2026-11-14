"""Learning demo: build a JWT by hand (no PyJWT) and prove it equals what jwt.encode() makes.

Run from backend/:  uv run python -m scripts.demo_jwt_by_hand
"""

import base64
import hashlib
import hmac
import json

import jwt

SECRET = "reception-stamp-demo-secret-0123456789"
payload = {"sub": "2", "exp": 1794380707}


def b64url(raw: bytes) -> str:
    # base64 made URL-safe: '+' -> '-', '/' -> '_', and padding '=' removed.
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


print("STEP 1. Header as JSON")
header_json = json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":"))
print("   ", header_json)

print("\nSTEP 2. Payload as JSON")
payload_json = json.dumps(payload, separators=(",", ":"))
print("   ", payload_json)

print("\nSTEP 3. Encode both with base64url (just re-spelling, NOT encryption)")
h = b64url(header_json.encode())
p = b64url(payload_json.encode())
print("    header  ->", h)
print("    payload ->", p)

print("\nSTEP 4. Signature = HMAC-SHA256( 'header.payload', SECRET )")
signing_input = f"{h}.{p}"
raw_sig = hmac.new(SECRET.encode(), signing_input.encode(), hashlib.sha256).digest()
s = b64url(raw_sig)
print("    signing input ->", signing_input)
print("    signature     ->", s)

print("\nSTEP 5. Join with dots")
by_hand = f"{h}.{p}.{s}"
print("   ", by_hand)

print("\nCOMPARE with PyJWT")
library = jwt.encode(payload, SECRET, algorithm="HS256")
print("    jwt.encode()  ->", library)
print("    identical?    ->", by_hand == library)

print("\nVERIFY by hand (what jwt.decode() does when a token comes back)")
vh, vp, vs = by_hand.split(".")
expected = b64url(hmac.new(SECRET.encode(), f"{vh}.{vp}".encode(), hashlib.sha256).digest())
print("    recomputed signature matches? ->", hmac.compare_digest(expected, vs))
