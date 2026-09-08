from flask import render_template, request, jsonify, session, current_app

from extensions import db
from models import Post, User
from constants import POST_CATEGORIES
from utils.security import login_required
from . import main_bp


@main_bp.route("/")
def feed():
    return render_template("index.html", categories=POST_CATEGORIES)


@main_bp.route("/api/feed")
def api_feed():
    """
    Public, anonymous feed. Never exposes author identity -- see
    Post.to_feed_dict(). Search matches the TITLE only (not the body),
    supports a category filter, and two sort modes.
    """
    page = request.args.get("page", 1, type=int)
    q = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    sort = request.args.get("sort", "recent")

    query = Post.query.filter_by(is_deleted=False)
    if q:
        query = query.filter(Post.title.ilike(f"%{q}%"))
    if category and category in POST_CATEGORIES:
        query = query.filter(Post.category == category)

    if sort == "trending":
        # Trending = most upvoted first, tie-broken by recency.
        query = query.outerjoin(Post.upvote_records)
        query = query.group_by(Post.id).order_by(
            db.func.count(Post.upvote_records).desc(), Post.created_at.desc()
        )
    else:
        query = query.order_by(Post.created_at.desc())

    pagination = query.paginate(
        page=page, per_page=current_app.config["POSTS_PER_PAGE"], error_out=False
    )
    viewer_id = session.get("user_id")
    return jsonify({
        "posts": [p.to_feed_dict(viewer_id=viewer_id) for p in pagination.items],
        "has_next": pagination.has_next,
        "page": pagination.page,
        "total": pagination.total,
    })


@main_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard/dashboard.html")


@main_bp.route("/api/profile")
@login_required
def api_profile():
    user = User.query.get_or_404(session["user_id"])
    return jsonify(user.to_public_dict())


@main_bp.route("/health")
def health():
    """Lightweight endpoint for Render / load balancer health checks."""
    return jsonify({"status": "ok"})
