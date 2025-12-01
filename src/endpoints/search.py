
from http import HTTPStatus
from flask import jsonify, request, g
from datetime import date

from src.mcp import search_agent, RecipeOutput
from src.extensions import db
from src.models import User, Post
from .blueprint import api_bp


@api_bp.post("/search")
def search():
    # get the user
    user: User | None = g.user

    # return if not authenticated
    if not user:
        return jsonify(error="Not authenticated"), HTTPStatus.UNAUTHORIZED

    # get the body and query parameter
    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()

    if not query:
        return jsonify(error="Missing Query"), HTTPStatus.BAD_REQUEST

    # run the agent synchronously based on the query
    try:
        result = search_agent.run_sync(query)
    except Exception:
        return jsonify(error="Error processing query"), HTTPStatus.INTERNAL_SERVER_ERROR

    # get the output
    output: RecipeOutput = result.output

    # add the output as a post to the database
    post = Post(
        user_id=user.id,
        hidden=True,
        recipe_title=output.title,
        recipe_message=output.message,
        recipe_image_url=output.image_url,
        recipe_video_url=output.video_url,
        date_posted=date.today()
    )

    # update the database
    db.session.add(post)
    db.session.commit()

    # return the AI reponse as well as the post id
    return jsonify(
        post_id=post.id,
        title=output.title,
        message=output.message,
        image_url=output.image_url,
        video_url=output.video_url,
    ), HTTPStatus.OK
