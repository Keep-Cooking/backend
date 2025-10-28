from http import HTTPStatus
from flask import Blueprint, jsonify, request, g, make_response
from sqlalchemy.exc import IntegrityError
import re
from .extensions import db
from .models import User
from .auth import Auth

api_bp = Blueprint("api", __name__)

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

    if not username or not email or not password:
        # return error if any field is not present
        return jsonify(error="Username, Email, and Password required"), HTTPStatus.BAD_REQUEST
    
    # check if the password is too short
    if len(password) < 8:
        return jsonify(error="Password must be at least 8 characters"), HTTPStatus.BAD_REQUEST
    
    # check if the password is too long
    if len(password) > 128:
        return jsonify(error="Password must be at most 128 characters"), HTTPStatus.BAD_REQUEST
    
    # enforce password minimum requirements (from: https://stackoverflow.com/a/21456918)
    # Minimum eight characters, at least one uppercase letter, one lowercase letter, one number, and one special character
    # maximum 128 characters
    password_pattern = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()\-_])[A-Za-z\d!@#$%^&*()\-_]{8,128}$"
    if not re.fullmatch(password_pattern, password):
        return jsonify(error="Password must have at least one uppercase letter, one lowercase letter, one number, and one special character"), HTTPStatus.BAD_REQUEST

    try:
        # pass username, email, and plaintext password to database
        # it gets hashed and salted and stored that way on the database
        user = User.create(username=username, email=email, password_plain=password)
    except IntegrityError:
        # If the username was already taken, rollback the transaction
        # and return a conflict error
        db.session.rollback()
        return jsonify(error="Username already taken"), HTTPStatus.CONFLICT

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


@api_bp.get("/me")
def me():
    # quick endpoint to check if the user is authenticated with jwt or not
    user: User | None = g.user

    if not user:
        return jsonify(authenticated=False), HTTPStatus.OK
    
    return jsonify(authenticated=True, user_id=user.id, username=user.username, email=user.email), HTTPStatus.OK
