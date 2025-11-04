import os
import pytest
from src.extensions import db
from flask.testing import FlaskClient
from flask import Flask

@pytest.fixture(scope="session")
def app():
    # configure the testing environment
    os.environ.setdefault("JWT_SECRET", "test-secret")
    os.environ.setdefault("COOKIE_SECURE", "false")
    os.environ.setdefault("ACCESS_TTL_HOURS", "24")
    os.environ.setdefault("GOOGLE_API_KEY", "test-key")
    os.environ.setdefault("THEMEALDB_API_KEY", "1")

    from src.app import app as flask_app

    # Set database to be in memory,
    # and set TESTING variable to true, if needed
    flask_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )

    # initialize the database
    db.init_app(flask_app)

    # empty and create the database
    with flask_app.app_context():
        db.drop_all()
        db.create_all()

    return flask_app


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    # test the client
    return app.test_client()
