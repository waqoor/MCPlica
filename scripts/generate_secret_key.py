import base64
import secrets

print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii"))
