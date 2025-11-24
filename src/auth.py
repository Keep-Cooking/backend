from datetime import datetime, timedelta, timezone
import os, jwt, string
from flask import request, Response
from pydantic import BaseModel, Field, EmailStr, field_validator


class Auth:
    __JWT_SECRET = os.environ.get("JWT_SECRET", os.urandom(64)) # custom JWT secret or random 64 bytes
    __ACCESS_TTL_HOURS = 24 # 24 hour TTL
    __COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", None)
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
    def set_cookie(resp: Response, name: str = __COOKIE_NAME, value: str = "", 
                   max_age: int = __ACCESS_TTL_HOURS * 3600, http_only: bool = True, path: str = "/") -> None:
        # set jwt token to the cookie
        resp.set_cookie(
            name, value,
            max_age=max_age,
            secure=Auth.__COOKIE_SECURE,
            httponly=http_only,
            domain=Auth.__COOKIE_DOMAIN,
            path=path,
        )

    @staticmethod
    def clear_cookie(resp: Response, name: str = __COOKIE_NAME, http_only: bool = True, path: str = "/") -> None:
        # clear the jwt token
        resp.set_cookie(name, "", expires=0, path=path, domain=Auth.__COOKIE_DOMAIN, secure=Auth.__COOKIE_SECURE, httponly=http_only)

    @staticmethod
    def validate_jwt(name: str = __COOKIE_NAME) -> int | None:
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
    

class UserRegistration(BaseModel):
    username: str = Field(...)
    email: EmailStr
    password: str = Field(...)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        if not v or len(v) < 1:
            raise ValueError('Username must have at least 1 character')
        if len(v) > 64:
            raise ValueError('Username must be at most 64 characters')
        return v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: EmailStr) -> EmailStr:
        # EmailStr validation happens first, then this
        if len(str(v)) > 255:
            raise ValueError('Please enter a valid email address')
        return v

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        # Check length constraints first
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')

        if len(v) > 128:
            raise ValueError('Password must be at most 128 characters')

        # Validate that it has at least one lowercase letter
        if not any(c.islower() for c in v):
            raise ValueError('Password must have at least one lowercase letter')

        # Validate that it has at least one uppercase letter
        if not any(c.isupper() for c in v):
            raise ValueError('Password must have at least one uppercase letter')

        # Validate numbers
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must have at least one number')

        # Validate special characters
        if not any(c in string.punctuation for c in v):
            raise ValueError('Password must have at least one special character')

        return v
