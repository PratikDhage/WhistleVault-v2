from sqlalchemy import or_

from flask import current_app, render_template, request, jsonify

from extensions import db
from models import Post, User, Report, Comment
from constants import POST_STATUSES
from utils.security import admin_required
from utils.storage import get_storage
from . import admin_bp


@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    return render_template("admin/dashboard.html")


@admin_bp.route("/posts/<post_id>")
@admin_required
def post_detail(post_id):
    Post.query.filter_by(id=post_id, is_deleted=False).first_or_404()
    return render_template("admin/post_detail.html", post_id=post_id, statuses=POST_STATUSES)


@admin_bp.route("/api/posts")
@admin_required
def api_posts():
    """
    Full moderation view -- the ONLY place in the app where author
    identity is attached to a post payload. Supports a "flagged only"
    triage filter (AI-flagged OR community-reported).
    """
    page = request.args.get("page", 1, type=int)
    q = (request.args.get("q") or "").strip()
    flagged_only = request.args.get("flagged_only") == "true"

    query = Post.query.filter_by(is_deleted=False)
    if q:
        query = query.filter(Post.title.ilike(f"%{q}%"))
    if flagged_only:
        query = query.outerjoin(Report, Report.post_id == Post.id).filter(
            or_(Post.ai_flagged == True, Report.id != None)  # noqa: E711,E712
        ).distinct()

    pagination = query.order_by(Post.created_at.desc()).paginate(page=page, per_page=20, error_out=False)
    return jsonify({
        "posts": [p.to_admin_dict() for p in pagination.items],
        "has_next": pagination.has_next,
        "page": pagination.page,
        "total": pagination.total,
    })


@admin_bp.route("/api/posts/<post_id>")
@admin_required
def api_post_detail(post_id):
    post = Post.query.filter_by(id=post_id, is_deleted=False).first_or_404()
    data = post.to_admin_dict()

    comments = (
        Comment.query.filter_by(post_id=post.id).order_by(Comment.created_at.asc()).all()
    )
    user_map = {u.id: u.username for u in User.query.filter(
        User.id.in_({c.user_id for c in comments})
    ).all()} if comments else {}

    nodes = {}
    for c in comments:
        nodes[c.id] = {
            "id": c.id,
            "content": "[deleted]" if c.is_deleted else c.content,
            "deleted": c.is_deleted,
            "created_at": c.created_at.isoformat() + "Z",
            "author_username": user_map.get(c.user_id, "[deleted account]"),
            "is_op": c.user_id == post.user_id,
            "replies": [],
        }
    roots = []
    for c in comments:
        node = nodes[c.id]
        if c.parent_id and c.parent_id in nodes:
            nodes[c.parent_id]["replies"].append(node)
        else:
            roots.append(node)

    data["comments"] = roots
    return jsonify(data)


@admin_bp.route("/api/stats")
@admin_required
def api_stats():
    flagged_posts = (
        Post.query.outerjoin(Report, Report.post_id == Post.id)
        .filter(Post.is_deleted == False)  # noqa: E712
        .filter(or_(Post.ai_flagged == True, Report.id != None))  # noqa: E711,E712
        .distinct()
        .count()
    )
    return jsonify({
        "total_users": User.query.count(),
        "verified_users": User.query.filter_by(is_verified=True).count(),
        "total_posts": Post.query.filter_by(is_deleted=False).count(),
        "deleted_posts": Post.query.filter_by(is_deleted=True).count(),
        "flagged_posts": flagged_posts,
    })


@admin_bp.route("/posts/<post_id>/delete", methods=["POST"])
@admin_required
def delete_post(post_id):
    post = Post.query.filter_by(id=post_id, is_deleted=False).first_or_404()

    storage = get_storage(current_app)
    for image in post.images:
        storage.delete(image.image_path)
    db.session.delete(post)
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/posts/<post_id>/status", methods=["POST"])
@admin_required
def update_status(post_id):
    post = Post.query.filter_by(id=post_id, is_deleted=False).first_or_404()
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in POST_STATUSES:
        return jsonify({"error": "Invalid status."}), 400
    post.set_status(status)
    db.session.commit()
    return jsonify({"success": True, "status": post.status})


@admin_bp.route("/comments/<comment_id>/delete", methods=["POST"])
@admin_required
def delete_comment(comment_id):
    comment = Comment.query.filter_by(id=comment_id).first_or_404()
    comment.is_deleted = True
    db.session.commit()
    return jsonify({"success": True})


@admin_bp.route("/users/<user_id>/deactivate", methods=["POST"])
@admin_required
def deactivate_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = False
    db.session.commit()
    return jsonify({"success": True})
