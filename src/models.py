from __future__ import annotations
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import date, datetime
from sqlalchemy import (
    String, Text, Integer, Boolean, ForeignKey, Date, Float,
    DateTime, func, event, case, select, Connection, Table
)

from flask import current_app
from pathlib import Path

from src.auth import UserRegistration
from src.extensions import db

ph = PasswordHasher(time_cost=3, memory_cost=64_000, parallelism=2)

class User(db.Model):
    __tablename__ = "auth"

    # unique id, automatically increments
    id: Mapped[int]         = mapped_column(primary_key=True, autoincrement=True)
    # required, unique, and indexed (to speed up lookup)
    username: Mapped[str]   = mapped_column(String(64), nullable=False, unique=True, index=True)
    # required
    email: Mapped[str]      = mapped_column(String(255), nullable=False)
    # required
    password: Mapped[str]   = mapped_column(String(512), nullable=False)
    images: Mapped[str]     = mapped_column(Text, default="[]")
    points: Mapped[int]     = mapped_column(Integer, default=0)
    level: Mapped[int]      = mapped_column(Integer, default=1)

    # whether or not this is an admin user
    admin: Mapped[bool]     = mapped_column(Boolean, default=False)

    posts: Mapped[list[Post]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )

    # when a user is deleted, their votes are deleted
    votes: Mapped[list["PostVote"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


    @staticmethod
    def create(user: UserRegistration) -> User:
        # create a new user, hashing + salting the plaintext password
        user = User(
            username=user.username,
            email=user.email,
            password=ph.hash(user.password),
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

    @staticmethod
    def level_for_points(points: int) -> int:
        # make a new level every 20 points
        return points // 20

    def apply_rating_reward(self, rating: int) -> bool:
        # safeguard
        rating = int(rating)
        if rating < 1:
            rating = 1
        if rating > 5:
            rating = 5

        self.points = (self.points or 0) + rating
        prev_level = self.level
        self.level = self.level_for_points(self.points)

        # return true for level up
        return self.level != prev_level


class Post(db.Model):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # map the parent user and userid
    user_id: Mapped[int] = mapped_column(ForeignKey("auth.id"), nullable=False, index=True)
    user: Mapped[User] = relationship(back_populates="posts")

    # votes on the post
    votes: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)

    # whether the post is hidden or shown
    hidden: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Flattened RecipeOutput fields
    recipe_title: Mapped[str] = mapped_column(String(255), nullable=False)
    recipe_message: Mapped[str] = mapped_column(Text, nullable=False)
    recipe_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    recipe_video_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # the date it was posted, used for sorting
    date_posted: Mapped[date] = mapped_column(Date, nullable=False, server_default=func.current_date(), index=True)

    # the uid of the image
    image_id: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)

    # rating from the AI from 1-5 flames
    rating: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)

    # created and updated fields just in case they're needed in the future
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    # votes for this post; delete when post is deleted
    vote_records: Mapped[list["PostVote"]] = relationship(
        back_populates="post",
        cascade="all, delete-orphan",
    )


@event.listens_for(Post, "after_delete")
def delete_post_image(mapper, connection, target: Post):
    # remove image file if exists
    if target.image_id:
        folder = current_app.config["IMAGE_UPLOAD_FOLDER"]
        path = Path(folder) / f"{target.image_id}.jpg"
        try:
            # remove the file
            path.unlink()
        except FileNotFoundError:
            # ignore file not found error, it's already gone
            pass


class PostVote(db.Model):
    __tablename__ = "post_votes"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("auth.id", ondelete="CASCADE"),
        primary_key=True,
    )
    post_id: Mapped[int] = mapped_column(
        ForeignKey("posts.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user: Mapped["User"] = relationship(back_populates="votes")
    post: Mapped["Post"] = relationship(back_populates="vote_records")

    upvote: Mapped[bool] = mapped_column(Boolean, nullable=False)


def _update_post_votes(connection: Connection, post: Post) -> None:
    """
    Recompute Post.votes from PostVote rows for the given post.
    Score = (#upvotes) - (#downvotes)
    """

    posts_table: Table = Post.__table__
    votes_table: Table = PostVote.__table__

    # score = (#upvotes) - (#downvotes)
    score_calc = (
        select(
            func.coalesce(
                func.sum(
                    case(
                        (votes_table.c.upvote.is_(True), 1),
                        else_=-1,
                    )
                ),
                0,
            )
        )
        .where(votes_table.c.post_id == post.id)
    )

    score = connection.execute(score_calc).scalar_one()

    update_command = (
        posts_table
        .update()
        .where(posts_table.c.id == post.id)
        .values(votes=int(score or 0))
    )

    connection.execute(update_command)


@event.listens_for(PostVote, "after_insert")
def postvote_after_insert(mapper, connection, target: PostVote):
    _update_post_votes(connection, target.post)


@event.listens_for(PostVote, "after_update")
def postvote_after_update(mapper, connection, target: PostVote):
    _update_post_votes(connection, target.post)


@event.listens_for(PostVote, "after_delete")
def postvote_after_delete(mapper, connection, target: PostVote):
    # target is detached but still has post_id
    _update_post_votes(connection, target.post)
