"""
Storage backend abstraction for post attachments.

STORAGE_BACKEND=local writes to MEDIA_FOLDER on disk -- fine for a single
Render instance or when MEDIA_FOLDER points at a mounted persistent disk.
STORAGE_BACKEND=s3 uploads to any S3-compatible object store (AWS S3,
Supabase Storage, Cloudflare R2, etc.), which is what you want once you
scale to multiple stateless instances behind a load balancer, since local
disk is not shared across instances.
"""
import os
import uuid
from werkzeug.utils import secure_filename


class StorageError(Exception):
    pass


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions


def _unique_name(original_filename: str) -> str:
    ext = secure_filename(original_filename).rsplit(".", 1)[-1].lower()
    return f"{uuid.uuid4().hex}.{ext}"


class LocalStorage:
    def __init__(self, media_folder):
        self.media_folder = media_folder
        os.makedirs(self.media_folder, exist_ok=True)

    def save(self, file_storage) -> str:
        name = _unique_name(file_storage.filename)
        path = os.path.join(self.media_folder, name)
        file_storage.save(path)
        return name  # stored as the relative "key"

    def delete(self, key: str):
        path = os.path.join(self.media_folder, key)
        if os.path.exists(path):
            os.remove(path)

    def path_for(self, key: str) -> str:
        return os.path.join(self.media_folder, key)


class S3Storage:
    """Thin wrapper -- requires boto3 to be installed and S3_* env vars set."""

    def __init__(self, bucket, region, access_key, secret_key):
        import boto3
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    def save(self, file_storage) -> str:
        key = _unique_name(file_storage.filename)
        self.client.upload_fileobj(
            file_storage,
            self.bucket,
            key,
            ExtraArgs={"ContentType": file_storage.mimetype or "application/octet-stream"},
        )
        return key

    def delete(self, key: str):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def url_for(self, key: str, expires_in=3600) -> str:
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_in,
        )


def get_storage(app):
    backend = app.config.get("STORAGE_BACKEND", "local")
    if backend == "s3":
        return S3Storage(
            bucket=app.config["S3_BUCKET"],
            region=app.config["S3_REGION"],
            access_key=app.config["S3_ACCESS_KEY"],
            secret_key=app.config["S3_SECRET_KEY"],
        )
    return LocalStorage(app.config["MEDIA_FOLDER"])
