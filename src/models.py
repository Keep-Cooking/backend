from __future__ import annotations
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from .extensions import db

ph = PasswordHasher(time_cost=3, memory_cost=64_000, parallelism=2)

class User(db.Model):
    __tablename__ = "auth"

    # unique id, automatically increments
    id       = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # required, unique, and indexed (to speed up lookup)
    username = db.Column(db.String(64), nullable=False, unique=True, index=True)
    # required
    email    = db.Column(db.String(255), nullable=False)
    # required
    password = db.Column(db.String(512), nullable=False)
    images   = db.Column(db.Text, default="[]")
    points   = db.Column(db.Integer, default=0)
    level    = db.Column(db.Integer, default=1)

    @staticmethod
    def create(username: str, email: str, password_plain: str) -> User:
        # create a new user, hashing + salting the plaintext password
        user = User(
            username=username,
            email=email,
            password=ph.hash(password_plain),
        )
        # add the user to the database
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def by_username(username: str) -> User | None:
        # find the user by the username
        return User.query.filter_by(username=username).first()

    def verify_and_maybe_rehash(self, password_plain: str) -> bool:
        # try to verify the password based on the plaintext password
        try:
            ph.verify(self.password, password_plain)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            # if it fails to verify, return false
            return False

        # if it's valid and needs to be rehashed, rehash it and commit those changes
        if ph.check_needs_rehash(self.password):
            self.password = ph.hash(password_plain)
            db.session.commit()

        # return true, verified
        return True
