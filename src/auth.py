from datetime import datetime, timedelta, timezone
import os, jwt
from flask import request

class Auth:
    __JWT_SECRET = os.environ.get("JWT_SECRET", os.urandom(64)) # custom JWT secret or random 64 bytes
    __ACCESS_TTL_HOURS = 24 # 24 hour TTL
    __COOKIE_SAMESITE = "Strict" # enforce Same-Site only
    __COOKIE_SECURE = os.getenv("SSL_ENABLE", "false").lower() == "true" # enable secure cookies if SSL is enabled
    __JWT_ALGORITHM = "HS512" # use HS512 algorithm
    __COOKIE_NAME = "access_token" # jwt cookie name

    @staticmethod
    def issue_access(user_id: int) -> str:
        # create a jwt token
        # set time of initialization, time of expiry, and identify user by id
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(user_id), # subject
            "iat": int(now.timestamp()), # time of initialization
            "exp": int((now + timedelta(hours=Auth.__ACCESS_TTL_HOURS)).timestamp()), # time of expiry
        }
        return jwt.encode(payload, Auth.__JWT_SECRET, algorithm=Auth.__JWT_ALGORITHM)

    @staticmethod
    def set_cookie(resp, name=__COOKIE_NAME, value="", max_age=__ACCESS_TTL_HOURS * 3600, http_only=True, path="/") -> None:
        # set jwt token to the cookie
        resp.set_cookie(
            name, value,
            max_age=max_age,
            secure=Auth.__COOKIE_SECURE,
            httponly=http_only,
            samesite=Auth.__COOKIE_SAMESITE,
            path=path,
        )

    @staticmethod
    def clear_cookie(resp, name=__COOKIE_NAME) -> None:
        # clear the jwt token
        resp.set_cookie(name, "", expires=0, path="/", samesite="Strict", secure=True, httponly=True)

    @staticmethod
    def validate_jwt(name=__COOKIE_NAME) -> int | None:
        # check if the jwt token exists in the cookie header
        token = request.cookies.get(name)

        # if not, return None
        if not token:
            return None

        # Try to decode the jwt token with the secret, enforcing fields to exist
        try:
            payload = jwt.decode(
                token,
                Auth.__JWT_SECRET,
                algorithms=[Auth.__JWT_ALGORITHM],
                # require subject, expiry time, and time of initialization
                options={"require": ["sub", "exp", "iat"]}, 
            )
        except jwt.PyJWTError:
            # If the jwt token failed to decode or is invalid, return None
            return None

        # return subject if it successfully decoded (valid jwt token)
        return int(payload["sub"])
