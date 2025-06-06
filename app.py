from flask import Flask, jsonify, Response
from config import Config
from utils.errors import register_error_handlers
from auth import require_api_key
print("LOADING APP.PY")
# Insert the parent directory (project root) into sys.path so that "src/" becomes visible.
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    from routes.documents import bp as documents_bp
    app.register_blueprint(documents_bp)

    register_error_handlers(app)

    @app.route("/")
    def root():
        return jsonify({
            "status": "success",
            "message": "Firestore Adapter service is running."
        })

    @app.route("/health")
    def health():
        return jsonify({
            "status": "success",
            "message": "Service is healthy."
        })

    @app.route('/protected')
    @require_api_key
    def protected():
        return {"status": "success"}, 200
    
    def test_with_empty_api_key_header(client):
        response = client.get('/protected', headers={"X-API-Key": ""})
        assert response.status_code == 401
        assert response.json["status"] == "error"
    # (or however your error payload is shaped)

    def test_with_lowercase_header_name(client):
        response = client.get('/protected', headers={"x-api-key": "test-key"})
        assert response.status_code == 200

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=app.config['DEBUG'], host="0.0.0.0", port=app.config['PORT'])
