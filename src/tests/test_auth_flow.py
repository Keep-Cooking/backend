import pytest
from http import HTTPStatus
from flask import Response
from flask.testing import FlaskClient

def test_signup_sets_cookie_and_me_is_authenticated(client: FlaskClient):
    # create a new user
    resp: Response = client.post(
        "/api/signup",
        json={"username": "alice", "email": "alice@example.com", "password": "Testing123!)@"},
    )
    # make sure that it successfully created a new user
    assert resp.status_code == HTTPStatus.CREATED

    # access_token cookie should be set
    set_cookie = resp.headers.get("Set-Cookie", "")
    assert "access_token=" in set_cookie

    # the client should have the cookie
    resp: Response = client.get("/api/me")
    assert resp.status_code == HTTPStatus.OK

    # make sure that the user data is correct
    data = resp.get_json()
    assert data["authenticated"] is True
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"


def test_duplicate_username_conflict(client: FlaskClient):
    # create a new user
    resp1 = client.post("/api/signup", json={"username": "bob", "email": "b1@example.com", "password": "Testing123!)@"})
    assert resp1.status_code == HTTPStatus.CREATED

    # Duplicate username, different email gives conflict error
    resp2 = client.post("/api/signup", json={"username": "bob", "email": "b2@example.com", "password": "Testing123!)@"})
    assert resp2.status_code == HTTPStatus.CONFLICT

    # Duplicate email, same username is ok
    # searching is only done by username
    resp2 = client.post("/api/signup", json={"username": "bob2", "email": "b1@example.com", "password": "Testing123!)@"})
    assert resp2.status_code == HTTPStatus.CREATED


def test_me_unauthenticated_when_no_cookie(client: FlaskClient):
    # check to make sure that /me endpoint 
    # returns False when there is no cookie
    resp: Response = client.get("/api/me")
    assert resp.status_code == HTTPStatus.OK
    assert resp.get_json()["authenticated"] is False


def test_logout_clears_cookie_and_me_is_false(client: FlaskClient):
    # create a new user
    client.post("/api/signup", json={"username": "erin", "email": "erin@example.com", "password": "Testing123!)@"})

    # make sure the user's authenticated
    assert client.get("/api/me").get_json()["authenticated"] is True

    # logout to clear the jwt token
    resp: Response = client.post("/api/logout")
    # make sure the user successfully logged out
    assert resp.status_code == HTTPStatus.OK

    # check to make sure that the user is not authenticated
    assert client.get("/api/me").get_json()["authenticated"] is False


def test_login_success_and_me(client: FlaskClient):
    # create a new user
    client.post("/api/signup", json={"username": "carol", "email": "carol@example.com", "password": "Testing123!)@"})

    # logout to clear cookie
    client.post("/api/logout")

    # make sure that the user isn't authenticated
    assert client.get("/api/me").get_json()["authenticated"] is False

    # login to the same user
    resp: Response = client.post("/api/login", json={"username": "carol", "password": "Testing123!)@"})
    assert resp.status_code == HTTPStatus.OK

    # make sure that the request returned a jwt token
    assert "access_token=" in resp.headers.get("Set-Cookie", "")

    # make sure that the user is authenticated
    resp: Response = client.get("/api/me")
    assert resp.get_json()["authenticated"] is True
    assert resp.get_json()["username"] == "carol"


def test_login_wrong_password(client: FlaskClient):
    # create a new user
    client.post("/api/signup", json={"username": "dave", "email": "dave@example.com", "password": "Testing123!)@"})

    # logout to clear cookie
    client.post("/api/logout")

    # try logging in but with the wrong password
    resp: Response = client.post("/api/login", json={"username": "dave", "password": "WrongPassword1234!)@"})
    # should return unauthorized error
    assert resp.status_code == HTTPStatus.UNAUTHORIZED

    # make sure that the user isn't authenticated
    assert client.get("/api/me").get_json()["authenticated"] is False


def test_login_missing_fields(client: FlaskClient):
    # try partial fields to make sure that the client sends Bad Request error
    # if some fields are missing

    resp: Response = client.post("/api/signup", json={"username": "x", "password": "Testing123!)@"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    data = resp.get_json()
    assert "error" in data
    assert data["error"] == "Please enter a valid email address"

    resp: Response = client.post("/api/signup", json={"password": "Testing123!)@", "email": "validuser@example.com"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    data = resp.get_json()
    assert "error" in data
    assert data["error"] == "Username must have at least 1 character"

    resp: Response = client.post("/api/signup", json={"username": "x", "email": "validuser@example.com"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    data = resp.get_json()
    assert "error" in data
    assert data["error"] == "Password must be at least 8 characters"


def test_signup_missing_fields(client: FlaskClient):
    # try partial fields to make sure that the client sends Bad Request error
    # if some fields are missing

    resp: Response = client.post("/api/signup", json={"username": "x"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    data = resp.get_json()
    assert "error" in data

    resp: Response = client.post("/api/signup", json={"password": "Testing123!)@"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    data = resp.get_json()
    assert "error" in data


def test_signup_invalid_email(client: FlaskClient):
    # Test invalid email format
    resp: Response = client.post(
        "/api/signup",
        json={"username": "testuser", "email": "not-an-email@test", "password": "Testing123!)@"},
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    data = resp.get_json()
    assert "error" in data
    assert data["error"] == "Please enter a valid email address"


@pytest.mark.parametrize(
    "username, email, password, expected_error",
    [
        (
            "A" * 65, # 65 chars
            "long@example.com",
            "Testing123!)@",
            "Username must be at most 64 characters",
        ),
        (
            "A",
            f"{"a" * 249}@b.com", # 256 chars
            "Testing123!)@",
            "Please enter a valid email address",
        ),
        (
            "short",
            "short@example.com",
            "Aa1!aa",  # 6 chars
            "Password must be at least 8 characters",
        ),
        (
            "toolong",
            "toolong@example.com",
            "A" * 129,  # 129 chars
            "Password must be at most 128 characters",
        ),
        (
            "noupper",
            "noupper@example.com",
            "lower1!lower",  # no uppercase
            "Password must have at least one uppercase letter",
        ),
        (
            "nolower",
            "nolower@example.com",
            "UPPER1!UP",  # no lowercase
            "Password must have at least one lowercase letter",
        ),
        (
            "nonumber",
            "nonumber@example.com",
            "NoDigits!AA",  # no digit
            "Password must have at least one number",
        ),
        (
            "nospecial",
            "nospecial@example.com",
            "Aa1aaaaa",  # no special char
            "Password must have at least one special character",
        ),
    ],
    ids=["username_too_long", "email_too_long", "too_short", "too_long", "missing_upper", "missing_lower", "missing_digit", "missing_special"],
)
def test_signup_rejects_invalid_registrations(client: FlaskClient, username: str, email: str, password: str, expected_error: str):
    resp: Response = client.post(
        "/api/signup",
        json={"username": username, "email": email, "password": password},
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    data = resp.get_json()
    assert "error" in data
    assert data["error"] == expected_error


def test_remove_account_authenticated(client: FlaskClient):
    # create a new user
    resp: Response = client.post(
        "/api/signup",
        json={"username": "test", "email": "test@example.com", "password": "Testing123!)@"},
    )
    # make sure that it successfully created a new user
    assert resp.status_code == HTTPStatus.CREATED

    # delete the user
    resp: Response = client.post("/api/remove-account")
    assert resp.status_code == HTTPStatus.OK

    # make sure the user isn't authenticated anymore
    resp: Response = client.get("/api/me")
    assert resp.status_code == HTTPStatus.OK
    data = resp.get_json()
    assert data["authenticated"] is False

    # make sure the user does not exist on the database anymore
    resp: Response = client.post("/api/login", json={"username": "test", "password": "Testing123!)@"})
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_remove_account_not_authenticated(client: FlaskClient):
    # try to delete an account when not authenticated
    resp: Response = client.post("/api/remove-account")
    assert resp.status_code == HTTPStatus.UNAUTHORIZED