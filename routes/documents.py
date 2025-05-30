from flask import Blueprint, request, jsonify, current_app
from auth import require_api_key
from firestore_client import FirestoreClient
from google.cloud import firestore
from google.api_core.exceptions import InvalidArgument

bp = Blueprint("documents", __name__)

def get_client():
    return FirestoreClient(current_app.config["FIRESTORE_CREDENTIALS"])

@bp.route("/documents/<collection>", methods=["GET"])
@require_api_key
def query_documents(collection):
    client = get_client()
    db = client.db
    query = db.collection(collection)

    # ---- 1. Build Filters ----
    filters = []
    for key, value in request.args.items():
        if key in {"limit", "offset", "order_by", "fields"}:
            continue
        elif key.endswith("_gte"):
            filters.append((key[:-4], ">=", _auto_type(value)))
        elif key.endswith("_lte"):
            filters.append((key[:-4], "<=", _auto_type(value)))
        elif key.endswith("_gt"):
            filters.append((key[:-3], ">", _auto_type(value)))
        elif key.endswith("_lt"):
            filters.append((key[:-3], "<", _auto_type(value)))
        elif key.endswith("_in"):
            # Split comma-separated list
            filters.append((key[:-3], "in", [_auto_type(x) for x in value.split(",")]))
        else:
            filters.append((key, "==", _auto_type(value)))
    # Apply filters to Firestore query
    try:
        for f in filters:
            query = query.where(*f)
    except InvalidArgument as e:
        return jsonify({"status": "error", "message": f"Invalid filter: {e}"}), 400

    # ---- 2. Sorting (order_by) ----
    order_by = request.args.get("order_by")
    if order_by:
        for field in order_by.split(","):
            direction = firestore.Query.DESCENDING if field.startswith("-") else firestore.Query.ASCENDING
            field_name = field.lstrip("-")
            query = query.order_by(field_name, direction=direction)

    # ---- 3. Pagination ----
    try:
        limit = int(request.args.get("limit", 20))
        if limit < 1 or limit > 1000:
            return jsonify({"status": "error", "message": "Limit must be between 1 and 1000"}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Limit must be an integer"}), 400

    try:
        offset = int(request.args.get("offset", 0))
        if offset < 0:
            return jsonify({"status": "error", "message": "Offset must be >= 0"}), 400
    except ValueError:
        return jsonify({"status": "error", "message": "Offset must be an integer"}), 400

    query = query.limit(limit)
    docs = query.stream()
    docs = list(docs)[offset:offset+limit]

    # ---- 4. Field Selection ----
    fields = request.args.get("fields")
    if fields:
        field_list = [f.strip() for f in fields.split(",")]
        data = [{k: v for k, v in doc.to_dict().items() if k in field_list} | {"id": doc.id} for doc in docs]
    else:
        data = [{**doc.to_dict(), "id": doc.id} for doc in docs]

    # ---- 5. Response ----
    return jsonify({
        "status": "success",
        "data": data,
        "limit": limit,
        "offset": offset,
        "count": len(data)
    })

def _auto_type(val):
    """Try to convert to int or float, else leave as str."""
    try:
        if "." in val:
            return float(val)
        else:
            return int(val)
    except (ValueError, TypeError):
        return val

@bp.route("/documents/<collection>", methods=["POST"])
@require_api_key
def create_document(collection):
    data = request.json
    client = get_client()
    result = client.create_document(collection, data)
    return jsonify({"status": "success", "data": result})

@bp.route("/documents/<collection>/<doc_id>", methods=["GET"])
@require_api_key
def read_document(collection, doc_id):
    client = get_client()
    doc = client.read_document(collection, doc_id)
    if doc:
        return jsonify({"status": "success", "data": doc})
    else:
        return jsonify({"status": "error", "message": "Not found"}), 404

@bp.route("/documents/<collection>/<doc_id>", methods=["PUT"])
@require_api_key
def update_document(collection, doc_id):
    data = request.json
    client = get_client()
    updated = client.update_document(collection, doc_id, data)
    if updated:
        return jsonify({"status": "success", "data": updated})
    else:
        return jsonify({"status": "error", "message": "Document not found"}), 404

@bp.route("/documents/<collection>/<doc_id>", methods=["DELETE"])
@require_api_key
def delete_document(collection, doc_id):
    client = get_client()
    result = client.delete_document(collection, doc_id)
    return jsonify({"status": "success", "data": result})
