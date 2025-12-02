from http import HTTPStatus
from flask import jsonify, request, g, make_response
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError

from src.extensions import db
from src.models import User
from src.auth import Auth, UserRegistration
from .blueprint import api_bp


@api_bp.before_request
def load_user():
    # runs before every request
    # checks if the request sent a jwt token and finds the user if so
    uid = Auth.validate_jwt()
    g.user = db.session.get(User, uid) if uid else None


@api_bp.post("/signup")
def signup():
    # Get json from body without erroring
    # Must send with mimetype/JSON
    # If there's nothing, data = {}
    data: dict = request.get_json(silent=True) or {}

    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    try:
        user_data = UserRegistration(
            username=username,
            email=email,
            password=password
        )
        # Validation passed, continue with registration
    except ValidationError as e:
        # Extract first error message for cleaner response
        error = e.errors()[0]
        error_msg = error['msg']

        # Custom message for email validation errors
        if error['loc'][0] == 'email' and error['type'] == 'value_error':
            error_msg = "Please enter a valid email address"
        else:
            # Remove Pydantic's "Value error, " prefix if present
            if error_msg.startswith("Value error, "):
                error_msg = error_msg[len("Value error, "):]

        return jsonify(error=error_msg), HTTPStatus.BAD_REQUEST

    try:
        # pass username, email, and plaintext password to database
        # it gets hashed and salted and stored that way on the database
        user = User.create(user_data)
    except IntegrityError:
        # If the username was already taken, rollback the transaction
        # and return a conflict error
        db.session.rollback()
        return jsonify(error="Username already taken"), HTTPStatus.CONFLICT

    # if the username is admin, give it admin perms lol
    if user.username == "admin":
        user.admin = True
        db.session.commit()

    # issue access with the subject being the user id
    token = Auth.issue_access(user.id)
    # Create a response with status CREATED
    resp = make_response(jsonify(message="Account created"), HTTPStatus.CREATED)
    # attach the cookie to the response
    Auth.set_cookie(resp, value=token)

    return resp


@api_bp.post("/login")
def login():
    # Get json from body without erroring
    # Must send with mimetype/JSON
    # If there's nothing, data = {}
    data: dict = request.get_json(silent=True) or {}

    # check if username and password exist in request data
    username = data.get("username", None)
    password = data.get("password", None)

    # if not, send bad request error
    if not username or not password:
        return jsonify(error="Username and Password required"), HTTPStatus.BAD_REQUEST

    # get the user by the username
    user = User.by_username(username)

    # check if the user exists and validate the password against the hashed password
    # rehash the password if necessary (i.e. argon2 parameters changed)
    if not user or not user.verify_and_maybe_rehash(password):
        return jsonify(error="Invalid credentials"), HTTPStatus.UNAUTHORIZED

    # issue access with the subject being the user id
    token = Auth.issue_access(user.id)
    # Create a response with status OK
    resp = make_response(jsonify(message="Successfully authenticated"), HTTPStatus.OK)
    # attach the cookie to the response
    Auth.set_cookie(resp, value=token)

    return resp


@api_bp.post("/logout")
def logout():
    # create a response with status OK
    resp = make_response(jsonify(message="Successfully logged out"), HTTPStatus.OK)
    # clear the cookie with the response
    Auth.clear_cookie(resp)
    return resp


@api_bp.post("/remove-account")
def remove_account():
    user: User | None = g.user

    # if not authenticated, return unauthorized
    if not user:
        return jsonify(error="Not authenticated"), HTTPStatus.UNAUTHORIZED

    # delete the user and all of their posts
    db.session.delete(user)
    db.session.commit()

    # create a response with status OK
    resp = make_response(jsonify(message="Successfully deleted account"), HTTPStatus.OK)

    # clear the cookie with the response to log the user out
    Auth.clear_cookie(resp)

    return resp


@api_bp.get("/me")
def me():
    # quick endpoint to check if the user is authenticated with jwt or not
    user: User | None = g.user

    if not user:
        return jsonify(authenticated=False), HTTPStatus.OK

    return jsonify(
        authenticated=True, 
        user_id=user.id, 
        username=user.username, 
        email=user.email, 
        admin=user.admin,
        points=user.points,
        level=user.level
    ), HTTPStatus.OK
