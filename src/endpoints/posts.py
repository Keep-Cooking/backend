from http import HTTPStatus
from flask import jsonify, request, g, url_for, current_app, send_from_directory
from sqlalchemy import asc, desc
from datetime import date
from pathlib import Path
from uuid import uuid4
from PIL import Image
from pydantic_ai import BinaryImage

from src.mcp import image_agent, RecipeOutput, ImageOutput
from src.extensions import db
from src.models import User, Post, PostVote
from .blueprint import api_bp


def is_valid_image(file_bytes: bytes):
    try:
        with Image.open(file_bytes) as img:
            # make sure its a proper image
            img.verify()
            # make sure its a jpeg
            return img.format.lower() != "jpeg"
    except (IOError, SyntaxError):
        return False


@api_bp.get("/my-posts")
def my_posts():
    user: User | None = g.user

    # check if the user is authenticated
    if not user:
        return jsonify(error="Not authenticated"), HTTPStatus.UNAUTHORIZED

    # get the posts by user id
    posts: list[Post] = (
        Post.query
        .filter_by(user_id=user.id)
        .order_by(Post.date_posted.desc())
        .all()
    )

    data = [
        {
            "id": post.id,
            "title": post.recipe_title,
            "image_url": (
                url_for("api.get_image", image_id=post.image_id, _external=True)
                if post.image_id else None
            ),
            "votes": post.votes,
            "rating": post.rating,
            "hidden": post.hidden,
        }
        for post in posts
    ]

    return jsonify(posts=data), HTTPStatus.OK


@api_bp.get("/posts/<int:post_id>")
def get_post(post_id: int):
    user: User | None = g.user
    post: Post | None = db.session.get(Post, post_id)

    if not post:
        return jsonify(error="Post not found"), HTTPStatus.NOT_FOUND

    # Only owner can see hidden posts
    if post.hidden and (not user or user.id != post.user_id):
        return jsonify(error="Post not found"), HTTPStatus.NOT_FOUND

    image_url = (
        url_for("api.get_image", image_id=post.image_id, _external=True)
        if post.image_id else None
    )

    return jsonify(
        id=post.id,
        user_id=post.user_id,
        username=post.user.username,
        recipe={
            "title": post.recipe_title,
            "message": post.recipe_message,
            "image_url": post.recipe_image_url,
            "video_url": post.recipe_video_url,
        },
        image_url=image_url,
        votes=post.votes,
        rating=post.rating,
        hidden=post.hidden,
        date_posted=post.date_posted.isoformat(),
    ), HTTPStatus.OK


@api_bp.get("/posts")
def list_posts():
    # example query:
    # use query builder to make this
    # https://api.keepcooking.recipes/posts?sort_by=(date_posted|votes|rating)?order=(asc|desc)?page=(page_number)?page_size=(page_size)?min_rating=(0..5|Null)?max_rating=(0..5|Null)

    sort_by = request.args.get("sort_by", "date_posted")
    order = request.args.get("order", "desc").lower()
    page = int(request.args.get("page", 1))
    page_size = min(int(request.args.get("page_size", 20)), 100)

    min_rating = request.args.get("min_rating")
    max_rating = request.args.get("max_rating")

    # search for posts that are not hidden
    query = Post.query.join(User).filter(Post.hidden.is_(False))

    # if min/max rating is specified,
    # filter results to a specific rating range
    if min_rating is not None:
        query = query.filter(Post.rating >= float(min_rating))
    if max_rating is not None:
        query = query.filter(Post.rating <= float(max_rating))

    # sort by votes, rating, or date posted
    if sort_by == "votes":
        sort_column = Post.votes
    elif sort_by == "rating":
        sort_column = Post.rating
    else:
        sort_column = Post.date_posted

    # sort in ascending or descending order
    if order == "asc":
        query = query.order_by(asc(sort_column))
    else:
        query = query.order_by(desc(sort_column))

    # paginate result
    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    # construct the result
    items = [
        {
            "id": post.id,
            "recipe": {
                "title": post.recipe_title,
                "message": post.recipe_message,
                "image_url": post.recipe_image_url,
                "video_url": post.recipe_video_url,
            },
            "image_url": (
                url_for("api.get_image", image_id=post.image_id, _external=True)
                if post.image_id else None
            ),
            "rating": post.rating,
            "votes": post.votes,
            "username": post.user.username,
            "date_posted": post.date_posted.isoformat(),
        }
        for post in pagination.items
    ]

    # send the paginated result
    return jsonify(
        page=pagination.page,
        page_size=page_size,
        total_pages=pagination.pages,
        total_items=pagination.total,
        items=items,
    ), HTTPStatus.OK


@api_bp.post("/posts/<int:post_id>/upvote")
def upvote_post(post_id: int):
    user: User | None = g.user

    # check if the user is authenticated
    if not user:
        return jsonify(error="Not authenticated"), HTTPStatus.UNAUTHORIZED

    # check if the post exists and isn't hidden
    post: Post | None = db.session.get(Post, post_id)
    if not post or post.hidden:
        return jsonify(error="Post not found"), HTTPStatus.NOT_FOUND

    # check if already voted
    existing_vote: PostVote = PostVote.query.filter_by(
        user_id=user.id,
        post_id=post.id
    ).first()

    # if the vote exists
    if existing_vote:
        # check if the current vote is a upvote
        if existing_vote.upvote:
            # if it is, return
            return jsonify(error="Already upvoted"), HTTPStatus.BAD_REQUEST
        
        # if it's a downvote, switch the vote to an upvote
        existing_vote.upvote = True
        # increment by 2 to negate the previous downvote
        post.votes += 2
    else:
        # create a new upvote
        vote = PostVote(user_id=user.id, post_id=post.id, upvote=True)
        # increment vote counter by 1
        post.votes += 1

        # add the vote to the database
        db.session.add(vote)

    # update the database
    db.session.commit()

    # return status
    return jsonify(
        message="Upvoted",
        post_id=post.id,
        votes=post.votes,
    ), HTTPStatus.OK


@api_bp.post("/posts/<int:post_id>/downvote")
def downvote_post(post_id: int):
    user: User | None = g.user

    # check if the user is authenticated
    if not user:
        return jsonify(error="Not authenticated"), HTTPStatus.UNAUTHORIZED

    # check if the post exists and isn't hidden
    post: Post | None = db.session.get(Post, post_id)
    if not post or post.hidden:
        return jsonify(error="Post not found"), HTTPStatus.NOT_FOUND

    # check if already voted
    existing_vote: PostVote = PostVote.query.filter_by(
        user_id=user.id,
        post_id=post.id
    ).first()

    # if the vote exists
    if existing_vote:
        # check if the current vote is a downvote
        if not existing_vote.upvote:
            # if it is, return
            return jsonify(error="Already downvoted"), HTTPStatus.BAD_REQUEST
        
        # if it's a upvote, switch the vote to a downvote
        existing_vote.upvote = False
        # decrement by 2 to negate the previous upvote
        post.votes -= 2
    else:
        # create a new upvote
        vote = PostVote(user_id=user.id, post_id=post.id, upvote=False)
        # decrement vote counter by 1
        post.votes -= 1

        # add the vote to the database
        db.session.add(vote)

    # update the database
    db.session.commit()

    # return status
    return jsonify(
        message="Downvoted",
        post_id=post.id,
        votes=post.votes,
    ), HTTPStatus.OK


@api_bp.delete("/posts/<int:post_id>")
def delete_post(post_id: int):
    user: User | None = g.user

    # check if the user is authenticated
    if not user:
        return jsonify(error="Not authenticated"), HTTPStatus.UNAUTHORIZED

    # get the post fromt he post id
    post: Post | None = db.session.get(Post, post_id)

    # check if the post exists
    if not post:
        return jsonify(error="Post not found"), HTTPStatus.NOT_FOUND

    # if the post is not owned by the user, they can't delete it
    if post.user_id != user.id:
        return jsonify(error="Not authorized"), HTTPStatus.FORBIDDEN

    # remove image file if exists
    if post.image_id:
        folder = current_app.config["IMAGE_UPLOAD_FOLDER"]
        path = Path(folder) / f"{post.image_id}.jpg"
        try:
            # remove the file
            path.unlink()
        except FileNotFoundError:
            # ignore file not found error, it's already gone
            pass

    # delete the element from the database
    db.session.delete(post)
    db.session.commit()

    # succesfully deleted
    return jsonify(message="Post deleted"), HTTPStatus.OK


@api_bp.post("/posts/<int:post_id>/publish")
def publish_post(post_id: int):
    user: User | None = g.user

    # check if the user is authenticated
    if not user:
        return jsonify(error="Not authenticated"), HTTPStatus.UNAUTHORIZED

    # check if the post exists
    post: Post | None = db.session.get(Post, post_id)
    if not post:
        return jsonify(error="Post not found"), HTTPStatus.NOT_FOUND

    # not the correct user
    if post.user_id != user.id:
        return jsonify(error="Not authorized"), HTTPStatus.FORBIDDEN

    # make the post visible
    post.hidden = False

    # update the date posted to now
    post.date_posted = date.today()

    # update the database
    db.session.commit()

    return jsonify(message="Post published", post_id=post.id), HTTPStatus.OK


@api_bp.post("/posts/<int:post_id>/generate-rating")
def generate_rating(post_id: int):
    user: User | None = g.user

    # check if the user is authenticated
    if not user:
        return jsonify(error="Not authenticated"), HTTPStatus.UNAUTHORIZED

    # get the post based on the post id
    post: Post | None = db.session.get(Post, post_id)

    # check if the post exists
    if not post:
        return jsonify(error="Post not found"), HTTPStatus.NOT_FOUND

    # check if the post belongs to the user
    if post.user_id != user.id:
        return jsonify(error="Not authorized"), HTTPStatus.FORBIDDEN

    # expecting multipart/form-data with field name "image"
    file = request.files.get("image")

    # check if the file was uploaded
    if not file or file.filename == "":
        return jsonify(error="No image uploaded"), HTTPStatus.BAD_REQUEST

    # check if the image is valid
    if not is_valid_image(file.stream):
        return jsonify(error="Invalid image format"), HTTPStatus.BAD_REQUEST 

    # create a uuid for the image
    image_id = str(uuid4())
    filename = f"{image_id}.jpg"

    # check if an image already exists
    if post.image_id:
        # delete the old image
        folder = current_app.config["IMAGE_UPLOAD_FOLDER"]
        path = Path(folder) / f"{post.image_id}.jpg"
        try:
            # remove the file
            path.unlink()
        except FileNotFoundError:
            # ignore file not found error, it's already gone
            pass

    # set the new image id
    post.image_id = image_id

    # generate a rating here
    try:
        result = image_agent.run_sync([
            "This is the recipe",
            RecipeOutput(
                title=post.recipe_title,
                message=post.recipe_message,
                image_url=post.recipe_image_url,
                video_url=post.recipe_video_url
            ),
            "And this is the image",
            BinaryImage(file.stream)
        ])
    except Exception:
        db.session.rollback()
        return jsonify(error="Error processing query"), HTTPStatus.INTERNAL_SERVER_ERROR

    output: ImageOutput = result.output

    # check if it was a valid rating
    if not output.valid_image:
        db.session.rollback()
        return jsonify(error="Invalid image submitted. Please take another picture and try again."), HTTPStatus.BAD_REQUEST

    # update the post's rating
    post.rating = output.rating

    # create the image folder if it doesnt already exist
    folder = Path(current_app.config["IMAGE_UPLOAD_FOLDER"])
    folder.mkdir(exist_ok=True)

    # save the image to the path
    path = folder / filename
    file.save(path)

    # add the changes
    db.session.commit()

    # generate a url for the image
    image_url = url_for("api.get_image", image_id=image_id, _external=True)

    # return the response, along with the model's reasoning
    return jsonify(
        message=output.response,
        post_id=post.id,
        image_url=image_url,
    ), HTTPStatus.OK


@api_bp.get("/images/<string:image_id>.jpg")
def get_image(image_id: str):
    user: User | None = g.user

    # lookup the Post from the image id
    post: Post | None = Post.query.filter_by(image_id=image_id).first()

    # not found
    if not post:
        return HTTPStatus.NOT_FOUND

    # if the post is hidden and the user id doesnt match the post's user id, return NOT FOUND
    if post.hidden and (not user or user.id != post.user_id):
        return HTTPStatus.NOT_FOUND

    # else, serve the image like normal
    folder = current_app.config["IMAGE_UPLOAD_FOLDER"]
    return send_from_directory(folder, f"{image_id}.jpg")
