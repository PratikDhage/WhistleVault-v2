import uuid
from datetime import datetime, timedelta

from extensions import db
from constants import POST_STATUSES


def gen_uuid():
    return str(uuid.uuid4())


class User(db.Model):
    """
    A registered whistleblower account.

    Identity is never exposed on public-facing views (see privacy_shield
    decorators in blueprints/posts and blueprints/admin). It exists in the
    DB purely so the *owner* can manage their own posts/comments and so an
    admin can moderate abuse -- not so other users can browse profiles.
    """
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    password_reset_token_hash = db.Column(db.String(64), nullable=True)

    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = db.Column(db.DateTime, nullable=True)

    posts = db.relationship("Post", backref="author", lazy="dynamic", cascade="all, delete-orphan")
    otps = db.relationship("OTP", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    upvotes = db.relationship("Upvote", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    comments = db.relationship("Comment", backref="author", lazy="dynamic", cascade="all, delete-orphan")
    bookmarks = db.relationship("Bookmark", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    reports = db.relationship("Report", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def to_public_dict(self):
        """Only what the *owner themself* should see about their own account."""
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "is_verified": self.is_verified,
            "member_since": self.created_at.strftime("%B %Y"),
            "post_count": self.posts.filter_by(is_deleted=False).count(),
            "total_upvotes_received": sum(
                p.upvote_count for p in self.posts.filter_by(is_deleted=False)
            ),
        }

    def __repr__(self):
        return f"<User {self.username}>"


class OTP(db.Model):
    """One-time password used for email verification at sign-up."""
    __tablename__ = "otps"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)
    consumed = db.Column(db.Boolean, default=False, nullable=False)

    @staticmethod
    def generate_code(length=6):
        import random
        import string
        return "".join(random.choices(string.digits, k=length))

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    @staticmethod
    def new_expiry(minutes=10):
        return datetime.utcnow() + timedelta(minutes=minutes)


class Post(db.Model):
    """
    An anonymous whistleblower submission.

    `user_id` is retained strictly for backend accountability (admin
    moderation, abuse takedown) and for populating "my posts" / bookmarks
    on the owner's own dashboard. It must NEVER be serialized into any
    public-facing feed/search/detail response or template -- only
    to_admin_dict() (used exclusively behind admin_required routes)
    attaches identity.
    """
    __tablename__ = "posts"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)

    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(64), nullable=False, default="Other", index=True)
    status = db.Column(db.String(20), nullable=False, default="open", index=True)

    # AI moderation triage (see utils/ai.py) -- best-effort, never blocking.
    ai_flagged = db.Column(db.Boolean, default=False, nullable=False, index=True)
    ai_flag_reason = db.Column(db.Text, nullable=True)

    view_count = db.Column(db.Integer, default=0, nullable=False)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False, index=True)
    deleted_by_admin = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    images = db.relationship(
        "PostImage", backref="post", lazy="joined",
        order_by="PostImage.position", cascade="all, delete-orphan",
    )
    upvote_records = db.relationship("Upvote", backref="post", lazy="dynamic", cascade="all, delete-orphan")
    comment_records = db.relationship("Comment", backref="post", lazy="dynamic", cascade="all, delete-orphan")
    bookmark_records = db.relationship("Bookmark", backref="post", lazy="dynamic", cascade="all, delete-orphan")
    report_records = db.relationship("Report", backref="post", lazy="dynamic", cascade="all, delete-orphan")

    @property
    def upvote_count(self):
        return self.upvote_records.count()

    @property
    def comment_count(self):
        return self.comment_records.count()

    @property
    def report_count(self):
        return self.report_records.count()

    def set_status(self, status: str):
        if status in POST_STATUSES:
            self.status = status

    def to_feed_dict(self, viewer_id=None):
        """
        Anonymous, public-safe card representation for the feed grid --
        title + first attached image, Reddit-style. No username, no
        email, no user_id.
        """
        thumb = self.images[0].image_url if self.images else None
        return {
            "id": self.id,
            "title": self.title,
            "thumbnail_url": thumb,
            "category": self.category,
            "status": self.status,
            "upvotes": self.upvote_count,
            "comment_count": self.comment_count,
            "view_count": self.view_count,
            "created_at": self.created_at.isoformat() + "Z",
            "upvoted_by_viewer": (
                viewer_id is not None
                and self.upvote_records.filter_by(user_id=viewer_id).first() is not None
            ),
        }

    def to_detail_dict(self, viewer_id=None):
        from utils.storage import get_storage
        storage = get_storage(current_app)

        image_urls = [
            storage.url_for(img.image_path)
            for img in sorted(self.images, key=lambda x: x.position)
        ]

        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "status": getattr(self, "status", "open"),
            "image_urls": image_urls,
            "created_at": self.created_at.isoformat() + "Z",
            "view_count": self.view_count,
            "upvotes": self.upvote_count,
            "upvoted_by_viewer": any(u.user_id == viewer_id for u in self.upvotes) if viewer_id else False,
            "bookmarked_by_viewer": any(b.user_id == viewer_id for b in self.bookmarks) if viewer_id else False,
        }

    def to_admin_dict(self):
        """Includes author identity and moderation signals -- admin use ONLY."""
        d = self.to_detail_dict()
        d.pop("bookmarked_by_viewer", None)
        d["author_username"] = self.author.username if self.author else "[deleted account]"
        d["author_id"] = self.user_id
        d["is_deleted"] = self.is_deleted
        d["ai_flagged"] = self.ai_flagged
        d["ai_flag_reason"] = self.ai_flag_reason
        d["report_count"] = self.report_count
        d["reports"] = [
            {
                "reason": report.reason or "Unspecified",
                "created_at": report.created_at.isoformat() + "Z",
            }
            for report in self.report_records.order_by(Report.created_at.desc()).all()
        ]
        return d

    def __repr__(self):
        return f"<Post {self.id} {self.title!r}>"


class PostImage(db.Model):
    """One of up to MAX_IMAGES_PER_POST attachments on a post."""
    __tablename__ = "post_images"

    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.String(36), db.ForeignKey("posts.id"), nullable=False, index=True)
    image_path = db.Column(db.String(512), nullable=False)  # storage key, not identity-linked
    position = db.Column(db.Integer, default=0, nullable=False)

    @property
    def image_url(self):
        from flask import current_app, url_for
        from utils.storage import get_storage

        if current_app.config.get("STORAGE_BACKEND") == "s3":
            return get_storage(current_app).url_for(self.image_path)
        return url_for("posts.media", filename=self.image_path)


class Comment(db.Model):
    """
    A comment on a post. Supports unlimited-depth threaded replies via
    `parent_id` (self-referential FK) -- the tree is assembled in Python
    by blueprints.posts.routes.build_comment_tree() from a single
    flat query, which is simpler and plenty fast at this scale than a
    recursive SQL CTE.

    Like posts, comments are anonymous to everyone except admins:
    to_dict() never includes the author's username; only the post's
    OWNER can be inferred as "OP" via an `is_op` flag computed by the
    caller (same user_id as the post, still never named).
    """
    __tablename__ = "comments"

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    post_id = db.Column(db.String(36), db.ForeignKey("posts.id"), nullable=False, index=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False, index=True)
    parent_id = db.Column(db.String(36), db.ForeignKey("comments.id"), nullable=True, index=True)

    content = db.Column(db.Text, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f"<Comment {self.id} on {self.post_id}>"


class Upvote(db.Model):
    """One upvote per (user, post) -- enforced with a unique constraint."""
    __tablename__ = "upvotes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    post_id = db.Column(db.String(36), db.ForeignKey("posts.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "post_id", name="uq_user_post_upvote"),
    )


class Bookmark(db.Model):
    """
    Personal 'save for later' -- visible only to the user who saved it.
    Framed here as a private watchlist of reports a reader wants to
    keep tabs on, without that interest being visible to anyone else.
    """
    __tablename__ = "bookmarks"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    post_id = db.Column(db.String(36), db.ForeignKey("posts.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "post_id", name="uq_user_post_bookmark"),
    )


class Report(db.Model):
    """
    Community flag on a post (distinct from an upvote) -- feeds the
    admin moderation queue so abusive or fake reports can be triaged by
    volume of community concern, not just an admin stumbling across them.
    """
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey("users.id"), nullable=False)
    post_id = db.Column(db.String(36), db.ForeignKey("posts.id"), nullable=False)
    reason = db.Column(db.String(300), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "post_id", name="uq_user_post_report"),
    )
