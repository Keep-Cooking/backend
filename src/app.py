import os
from flask import Flask
from flask_cors import CORS
from .endpoints import api_bp
from .extensions import db

# API Host, default to 0.0.0.0 if not specified
API_HOST = os.getenv("API_HOST", "0.0.0.0")
# API Port, default to 8000 if not specified
API_PORT = int(os.getenv("API_PORT", "8000"))
# Whether the stage is development or production
DEV = os.getenv("FLASK_STAGE", "dev") == "dev"

# if CORS_ALLOW_ORIGINS specified, use those for cors
if _cors_allow_origins := os.getenv("CORS_ALLOW_ORIGINS", "").strip():
    CORS_ORIGINS = [origin.strip() for origin in _cors_allow_origins.split(",") if origin.strip()]
else:
    # if not, use the FRONTEND_URL
    # if FRONTEND_URL is not specified, use localhost
    frontend_url = os.getenv("FRONTEND_URL")
    CORS_ORIGINS = [frontend_url] if frontend_url else ["http://localhost:3000", "http://127.0.0.1:3000"]

# Create flask app
app = Flask(__name__)

# Add cors to all api routes
CORS(app, resources={r"/api/*": {"origins": CORS_ORIGINS}}, supports_credentials=True)
# Register endpoints with the app
app.register_blueprint(api_bp, url_prefix="/api")

if __name__ == "__main__":
    app.config.update(
        # put database at /app/src/data/auth.db
        SQLALCHEMY_DATABASE_URI="sqlite:////app/src/data/auth.db",
        # dont track modifications (causes a lot of unnecessary overhead)
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        # secret key (random)
        SECRET_KEY=os.urandom(32).hex()
    )

    # initialize the database with the flask app
    db.init_app(app)

    # create the database on app initialization
    with app.app_context():
        db.create_all()

    # check if SSL is enabled
    # default to false if not specified
    ssl_enable = os.getenv("SSL_ENABLE", "false").lower() == "true"

    ssl_context = None
    if ssl_enable:
        # if ssl is enabled, get the cert and key paths
        cert = os.getenv("SSL_CERT_PATH")
        key = os.getenv("SSL_KEY_PATH")
        # if they are not specified, throw a runtime error
        if not (cert and key):
            raise RuntimeError("SSL_ENABLE=true but SSL_CERT_PATH/SSL_KEY_PATH not set")
        # if they are, build a ssl_context with the paths
        ssl_context = (cert, key)

    # start the flask app
    app.run(host=API_HOST, port=API_PORT, debug=DEV, ssl_context=ssl_context)
