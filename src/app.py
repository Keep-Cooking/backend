import os
from flask import Flask
from flask_cors import CORS
from urllib.parse import urlparse

from src.endpoints import api_bp
from src.extensions import db

# API Host, default to 0.0.0.0 if not specified
API_HOST = os.getenv("API_HOST", "0.0.0.0")
# API Port, default to 8000 if not specified
API_PORT = int(os.getenv("API_PORT", "8000"))
# Whether the stage is development or production
DEV = os.getenv("FLASK_STAGE", "dev") == "dev"
# Wheter or not SSL is enabled
SSL_ENABLE = os.getenv("SSL_ENABLE", "false").lower() == "true"

# apply CORS to the frontend url
frontend_url = os.getenv("FRONTEND_URL")
CORS_ORIGINS = [frontend_url] if frontend_url else ["http://localhost:3000"]

api_base = os.getenv(
    "API_BASE",
    f"{('http', 'https')[SSL_ENABLE]}://localhost:{API_PORT}",
)
parsed = urlparse(api_base)


def create_app():
    app = Flask(__name__)

    # Core config
    app.config.update(
        # put database at /app/src/data/auth.db
        SQLALCHEMY_DATABASE_URI="sqlite:////app/src/data/auth.db",
        # dont track modifications (causes a lot of unnecessary overhead)
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # secret key (random)
        SECRET_KEY=os.urandom(32).hex(),
        # images location
        IMAGE_UPLOAD_FOLDER="/app/src/data/images",
        # set max file size to 16Mb
        MAX_CONTENT_LENGTH=16 * 1000 * 1000,

        # e.g. "localhost:8000" or "api.keepcooking.recipes"
        SERVER_NAME=parsed.netloc,
        # e.g. "http" or "https"
        PREFERRED_URL_SCHEME=parsed.scheme,
    )

    # Init extensions
    db.init_app(app)

    # Blueprints & CORS
    CORS(app, resources={r"/api/*": {"origins": CORS_ORIGINS}}, supports_credentials=True)
    app.register_blueprint(api_bp, url_prefix="/api")

    # Create DB tables once per process startup
    with app.app_context():
        db.create_all()

    return app

app = create_app()

if __name__ == "__main__":
    ssl_context = None
    if SSL_ENABLE:
        cert = os.getenv("SSL_CERT_PATH")
        key = os.getenv("SSL_KEY_PATH")
        # if they are not specified, throw a runtime error
        if not (cert and key):
            raise RuntimeError("SSL_ENABLE=true but SSL_CERT_PATH/SSL_KEY_PATH not set")
        # if they are, build a ssl_context with the paths
        ssl_context = (cert, key)

    # start the flask app
    app.run(host=API_HOST, port=API_PORT, debug=DEV, ssl_context=ssl_context, threaded=True)
