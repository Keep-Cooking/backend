from http import HTTPStatus

def test_signup_sets_cookie_and_me_is_authenticated(client):
    # create a new user
    resp = client.post(
        "/api/signup",
        json={"username": "alice", "email": "alice@example.com", "password": "test"},
    )
    # make sure that it successfully created a new user
    assert resp.status_code == HTTPStatus.CREATED

    # access_token cookie should be set
    set_cookie = resp.headers.get("Set-Cookie", "")
    assert "access_token=" in set_cookie

    # the client should have the cookie
    resp = client.get("/api/me")
    assert resp.status_code == HTTPStatus.OK

    # make sure that the user data is correct
    data = resp.get_json()
    assert data["authenticated"] is True
    assert data["username"] == "alice"
    assert data["email"] == "alice@example.com"


def test_duplicate_username_conflict(client):
    # create a new user
    resp1 = client.post("/api/signup", json={"username": "bob", "email": "b1@example.com", "password": "pw"})
    assert resp1.status_code == HTTPStatus.CREATED

    # Duplicate username, different email gives conflict error
    resp2 = client.post("/api/signup", json={"username": "bob", "email": "b2@example.com", "password": "pw"})
    assert resp2.status_code == HTTPStatus.CONFLICT

    # Duplicate email, same username is ok
    # searching is only done by username
    resp2 = client.post("/api/signup", json={"username": "bob2", "email": "b1@example.com", "password": "pw"})
    assert resp2.status_code == HTTPStatus.CREATED


def test_me_unauthenticated_when_no_cookie(client):
    # check to make sure that /me endpoint 
    # returns False when there is no cookie
    resp = client.get("/api/me")
    assert resp.status_code == HTTPStatus.OK
    assert resp.get_json()["authenticated"] is False


def test_logout_clears_cookie_and_me_is_false(client):
    # create a new user
    client.post("/api/signup", json={"username": "erin", "email": "erin@example.com", "password": "pw"})

    # make sure the user's authenticated
    assert client.get("/api/me").get_json()["authenticated"] is True

    # logout to clear the jwt token
    resp = client.post("/api/logout")
    # make sure the user successfully logged out
    assert resp.status_code == HTTPStatus.OK

    # check to make sure that the user is not authenticated
    assert client.get("/api/me").get_json()["authenticated"] is False


def test_login_success_and_me(client):
    # create a new user
    client.post("/api/signup", json={"username": "carol", "email": "carol@example.com", "password": "pw123"})

    # logout to clear cookie
    client.post("/api/logout")

    # make sure that the user isn't authenticated
    assert client.get("/api/me").get_json()["authenticated"] is False

    # login to the same user
    resp = client.post("/api/login", json={"username": "carol", "password": "pw123"})
    assert resp.status_code == HTTPStatus.OK

    # make sure that the request returned a jwt token
    assert "access_token=" in resp.headers.get("Set-Cookie", "")

    # make sure that the user is authenticated
    resp = client.get("/api/me")
    assert resp.get_json()["authenticated"] is True
    assert resp.get_json()["username"] == "carol"


def test_login_wrong_password(client):
    # create a new user
    client.post("/api/signup", json={"username": "dave", "email": "dave@example.com", "password": "secret"})

    # logout to clear cookie
    client.post("/api/logout")

    # try logging in but with the wrong password
    resp = client.post("/api/login", json={"username": "dave", "password": "nope"})
    # should return unauthorized error
    assert resp.status_code == HTTPStatus.UNAUTHORIZED

    # make sure that the user isn't authenticated
    assert client.get("/api/me").get_json()["authenticated"] is False


def test_login_missing_fields(client):
    # try partial fields to make sure that the client sends Bad Request error
    # if some fields are missing

    resp = client.post("/api/signup", json={"username": "x", "password": "x"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST

    resp = client.post("/api/signup", json={"password": "x", "email": "x"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST

    resp = client.post("/api/signup", json={"username": "x", "email": "x"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST


def test_signup_missing_fields(client):
    # try partial fields to make sure that the client sends Bad Request error
    # if some fields are missing

    resp = client.post("/api/signup", json={"username": "x"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST

    resp = client.post("/api/signup", json={"password": "x"})
    assert resp.status_code == HTTPStatus.BAD_REQUEST
