from flask import (
    render_template, request, redirect, url_for, session, flash,
    jsonify, current_app, send_from_directory, abort
)

from extensions import db, limiter
from models import Post, PostImage, Comment, Upvote, Bookmark, Report
from constants import (
    POST_CATEGORIES, MAX_IMAGES_PER_POST, MAX_COMMENT_LENGTH,
    MAX_TITLE_LENGTH, MAX_CONTENT_LENGTH, REPORT_REASONS,
)
from utils.security import login_required
from utils.storage import get_storage, allowed_file, StorageError
from utils.ai import analyze_post
from . import posts_bp


def _current_user_id():
    return session.get("user_id")


# ---------------------------------------------------------------------
# Comment tree assembly
# ---------------------------------------------------------------------

def _serialize_comment(comment, post_owner_id):
    return {
        "id": comment.id,
        "content": "[deleted]" if comment.is_deleted else comment.content,
        "deleted": comment.is_deleted,
        "created_at": comment.created_at.isoformat() + "Z",
        "is_op": comment.user_id == post_owner_id,
        "is_mine": comment.user_id == _current_user_id(),
        "replies": [],
    }


def build_comment_tree(post):
    """
    Loads every comment on a post with a single query and assembles the
    (unlimited-depth) reply tree in memory. Simpler and fast enough at
    this scale compared to a recursive SQL CTE.
    """
    comments = (
        Comment.query.filter_by(post_id=post.id)
        .order_by(Comment.created_at.asc())
        .all()
    )
    nodes = {c.id: _serialize_comment(c, post.user_id) for c in comments}
    roots = []
    for c in comments:
        node = nodes[c.id]
        if c.parent_id and c.parent_id in nodes:
            nodes[c.parent_id]["replies"].append(node)
        else:
            roots.append(node)
    return roots


# ---------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------

@posts_bp.route("/create", methods=["GET", "POST"])
@login_required
@limiter.limit("20 per hour")
def create():
    if request.method == "GET":
        return render_template("posts/create.html", categories=POST_CATEGORIES)

    title = (request.form.get("title") or "").strip()
    content = (request.form.get("content") or "").strip()
    chosen_category = (request.form.get("category") or "").strip()

    errors = []
    if not title or len(title) < 5:
        errors.append("Title must be at least 5 characters.")
    if len(title) > MAX_TITLE_LENGTH:
        errors.append(f"Title must be under {MAX_TITLE_LENGTH} characters.")
    if not content or len(content) < 5:
        errors.append("Please provide more detail (at least 5 characters).")
    if len(content) > MAX_CONTENT_LENGTH:
        errors.append(f"Post is too long ({MAX_CONTENT_LENGTH} character max).")

    # Retrieve files from 'attachments'
    files = [f for f in request.files.getlist("attachments") if f and f.filename]
    if len(files) > MAX_IMAGES_PER_POST:
        errors.append(f"You can attach at most {MAX_IMAGES_PER_POST} images.")
    for f in files:
        if not allowed_file(f.filename, current_app.config["ALLOWED_IMAGE_EXTENSIONS"]):
            errors.append(f"Unsupported file type: {f.filename}. Allowed: png, jpg, jpeg, gif, webp.")

    if errors:
        for e in errors:
            flash(e, "error")
        return render_template(
            "posts/create.html", categories=POST_CATEGORIES, title=title, content=content
        ), 400

    # Server-side AI moderation pass
    analysis = analyze_post(current_app, title, content)
    final_category = chosen_category if chosen_category in POST_CATEGORIES else analysis.category

    post = Post(
        user_id=_current_user_id(),
        title=title,
        content=content,
        category=final_category,
        ai_flagged=analysis.flagged,
        ai_flag_reason=analysis.flag_reason or None,
    )
    db.session.add(post)
    db.session.flush()  # assigns post.id before saving images

    if files:
        try:
            storage = get_storage(current_app)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Storage configuration is invalid")
            flash("Image storage is not configured correctly. Please try again later.", "error")
            return render_template(
                "posts/create.html", categories=POST_CATEGORIES, title=title, content=content
            ), 503

        saved_keys = []
        for position, f in enumerate(files):
            try:
                key = storage.save(f)
                saved_keys.append(key)
                db.session.add(PostImage(post_id=post.id, image_path=key, position=position))
            except (StorageError, Exception):
                db.session.rollback()
                for saved_key in saved_keys:
                    try:
                        storage.delete(saved_key)
                    except Exception:
                        current_app.logger.exception("Failed to clean up uploaded image: %s", saved_key)
                current_app.logger.exception("Post image upload failed for file: %s", f.filename)
                flash("The image could not be uploaded. Check storage configuration and try again.", "error")
                return render_template(
                    "posts/create.html", categories=POST_CATEGORIES, title=title, content=content
                ), 503

    db.session.commit()

    if analysis.available and analysis.pii_detected and analysis.pii_warning:
        flash(f"Heads up: {analysis.pii_warning}", "error")

    flash("Your submission has been posted anonymously.", "success")
    return redirect(url_for("posts.detail", post_id=post.id))


@posts_bp.route("/api/analyze", methods=["POST"])
@login_required
@limiter.limit("15 per hour")
def api_analyze():
    """
    Live, pre-submit 'Check with AI' button on the create-post page.
    Returns a category suggestion and a PII heads-up only.
    """
    data = request.get_json(silent=True) or {}
    title = (data.get("title") or "").strip()
    content = (data.get("content") or "").strip()
    if not title and not content:
        return jsonify({"error": "Nothing to analyze yet."}), 400

    analysis = analyze_post(current_app, title, content)
    return jsonify({
        "available": analysis.available,
        "category": analysis.category,
        "pii_detected": analysis.pii_detected,
        "pii_warning": analysis.pii_warning,
    })


# ---------------------------------------------------------------------
# Detail page
# ---------------------------------------------------------------------

@posts_bp.route("/<post_id>")
def detail(post_id):
    post = Post.query.filter_by(id=post_id, is_deleted=False).first_or_404()
    return render_template("posts/detail.html", post_id=post.id)


@posts_bp.route("/<post_id>/api")
def api_detail(post_id):
    post = Post.query.filter_by(id=post_id, is_deleted=False).first_or_404()

    viewed = session.get("viewed_post_ids", [])
    if post_id not in viewed:
        post.view_count += 1
        viewed.append(post_id)
        session["viewed_post_ids"] = viewed[-500:]
        db.session.commit()

    viewer_id = _current_user_id()
    data = post.to_detail_dict(viewer_id=viewer_id)
    data["comments"] = build_comment_tree(post)
    return jsonify(data)


# ---------------------------------------------------------------------
# Upvote / bookmark / report
# ---------------------------------------------------------------------

@posts_bp.route("/<post_id>/upvote", methods=["POST"])
@login_required
@limiter.limit("60 per hour")
def upvote(post_id):
    post = Post.query.filter_by(id=post_id, is_deleted=False).first()
    if not post:
        return jsonify({"error": "Post not found."}), 404

    uid = _current_user_id()
    existing = Upvote.query.filter_by(user_id=uid, post_id=post.id).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"upvoted": False, "upvotes": post.upvote_count})

    db.session.add(Upvote(user_id=uid, post_id=post.id))
    db.session.commit()
    return jsonify({"upvoted": True, "upvotes": post.upvote_count})


@posts_bp.route("/<post_id>/bookmark", methods=["POST"])
@login_required
@limiter.limit("60 per hour")
def bookmark(post_id):
    post = Post.query.filter_by(id=post_id, is_deleted=False).first()
    if not post:
        return jsonify({"error": "Post not found."}), 404

    uid = _current_user_id()
    existing = Bookmark.query.filter_by(user_id=uid, post_id=post.id).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"bookmarked": False})

    db.session.add(Bookmark(user_id=uid, post_id=post.id))
    db.session.commit()
    return jsonify({"bookmarked": True})


@posts_bp.route("/<post_id>/report", methods=["POST"])
@login_required
@limiter.limit("10 per hour")
def report(post_id):
    post = Post.query.filter_by(id=post_id, is_deleted=False).first()
    if not post:
        return jsonify({"error": "Post not found."}), 404

    reason = ((request.get_json(silent=True) or {}).get("reason") or "").strip()
    if reason not in REPORT_REASONS:
        return jsonify({"error": "Choose a valid reason for reporting this post."}), 400
    uid = _current_user_id()
    existing = Report.query.filter_by(user_id=uid, post_id=post.id).first()

    if existing:
        existing.reason = reason
        db.session.commit()
        return jsonify({"reported": True, "already_reported": True})

    db.session.add(Report(user_id=uid, post_id=post.id, reason=reason))
    db.session.commit()
    return jsonify({"reported": True, "already_reported": False})


@posts_bp.route("/bookmarked", methods=["GET"])
@login_required
def bookmarked():
    page = request.args.get("page", 1, type=int)
    uid = _current_user_id()
    pagination = (
        Post.query.join(Bookmark, Bookmark.post_id == Post.id)
        .filter(Bookmark.user_id == uid, Post.is_deleted == False)
        .order_by(Bookmark.created_at.desc())
        .paginate(page=page, per_page=current_app.config["POSTS_PER_PAGE"], error_out=False)
    )
    return jsonify({
        "posts": [p.to_feed_dict(viewer_id=uid) for p in pagination.items],
        "has_next": pagination.has_next,
        "page": pagination.page,
    })


# ---------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------

@posts_bp.route("/<post_id>/comments", methods=["POST"])
@login_required
@limiter.limit("30 per hour")
def add_comment(post_id):
    post = Post.query.filter_by(id=post_id, is_deleted=False).first()
    if not post:
        return jsonify({"error": "Post not found."}), 404

    data = request.get_json(silent=True) or {}
    content = (data.get("content") or "").strip()
    parent_id = data.get("parent_id")

    if not content:
        return jsonify({"error": "Comment cannot be empty."}), 400
    if len(content) > MAX_COMMENT_LENGTH:
        return jsonify({"error": f"Comment is too long ({MAX_COMMENT_LENGTH} character max)."}), 400

    if parent_id:
        parent = Comment.query.filter_by(id=parent_id, post_id=post.id).first()
        if not parent:
            return jsonify({"error": "Original comment not found."}), 404

    comment = Comment(
        post_id=post.id, user_id=_current_user_id(), parent_id=parent_id or None, content=content
    )
    db.session.add(comment)
    db.session.commit()

    return jsonify(_serialize_comment(comment, post.user_id)), 201


@posts_bp.route("/comments/<comment_id>/delete", methods=["POST"])
@login_required
def delete_own_comment(comment_id):
    """Owners may delete their own comments; content becomes '[deleted]' but the thread stays intact."""
    comment = Comment.query.filter_by(id=comment_id, user_id=_current_user_id()).first()
    if not comment:
        return jsonify({"error": "Comment not found."}), 404
    comment.is_deleted = True
    db.session.commit()
    return jsonify({"success": True})


# ---------------------------------------------------------------------
# Owner post management
# ---------------------------------------------------------------------

@posts_bp.route("/mine", methods=["GET"])
@login_required
def mine():
    page = request.args.get("page", 1, type=int)
    pagination = (
        Post.query.filter_by(user_id=_current_user_id(), is_deleted=False)
        .order_by(Post.created_at.desc())
        .paginate(page=page, per_page=current_app.config["POSTS_PER_PAGE"], error_out=False)
    )
    return jsonify({
        "posts": [p.to_feed_dict(viewer_id=_current_user_id()) for p in pagination.items],
        "has_next": pagination.has_next,
        "page": pagination.page,
    })


@posts_bp.route("/<post_id>/delete", methods=["POST"])
@login_required
def delete_own(post_id):
    """Owners permanently delete their posts and attached media."""
    post = Post.query.filter_by(id=post_id, user_id=_current_user_id(), is_deleted=False).first()
    if not post:
        abort(404)

    storage = get_storage(current_app)
    for image in post.images:
        try:
            storage.delete(image.image_path)
        except Exception:
            current_app.logger.exception("Failed to delete media file: %s", image.image_path)
            
    db.session.delete(post)
    db.session.commit()
    flash("Post deleted.", "success")
    return redirect(url_for("main.dashboard"))


@posts_bp.route("/media/<path:filename>")
def media(filename):
    """
    Serves locally-stored attachments. Filenames are randomly generated
    UUIDs at upload time.
    """
    if current_app.config.get("STORAGE_BACKEND") != "local":
        abort(404)
    return send_from_directory(current_app.config["MEDIA_FOLDER"], filename)