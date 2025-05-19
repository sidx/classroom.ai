from enum import Enum

SIGNED_URL_DEFAULT_EXPIRATION_TIME = 60 * 60 * 24 * 7  # 1 week
SIGNED_URL_REDIS_EXPIRATION_TIME = 60 * 60 * 24 * 6  # 6 days


class SignMethod(str, Enum):
    GET = "get"
    PUT = "put"


sign_method_signed_url_expiry_mapping = {
    SignMethod.GET: SIGNED_URL_DEFAULT_EXPIRATION_TIME,
    SignMethod.PUT: 60 * 60  # 1 hour
}


AutoCompleteModel = {
    "openai": "gpt-4o",
    "claude": "claude-3-5-sonnet-20240620"
}