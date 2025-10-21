from flask import Blueprint, jsonify, request


api_bp = Blueprint("api", __name__)

# example endpoint (replace with real endpoints)
@api_bp.get("/example")
def example():
    return jsonify({"status": "ok"}), 200
