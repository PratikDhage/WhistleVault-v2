import os
import uuid
from werkzeug.utils import secure_filename
from botocore.config import Config
from botocore.exceptions import ClientError


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
        return name

    def delete(self, key: str):
        path = os.path.join(self.media_folder, key)
        if os.path.exists(path):
            os.remove(path)

    def path_for(self, key: str) -> str:
        return os.path.join(self.media_folder, key)


class S3Storage:
    """S3 wrapper configured for Supabase Storage, AWS S3, or Cloudflare R2."""

    def __init__(self, bucket, region, endpoint, access_key, secret_key):
        import boto3

        self.bucket = bucket
        
        # Required for Supabase S3 compatibility: path-style addressing and s3v4 signature
        config = Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
        )

        self.client = boto3.client(
            "s3",
            region_name=region or "us-east-1",
            endpoint_url=endpoint or None,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=config,
        )

    def save(self, file_storage) -> str:
        try:
            key = _unique_name(file_storage.filename)
            
            # Reset file pointer to beginning before streaming to S3
            if hasattr(file_storage, "seek"):
                file_storage.seek(0)

            content_type = getattr(file_storage, "mimetype", None) or "application/octet-stream"

            self.client.upload_fileobj(
                file_storage.stream if hasattr(file_storage, "stream") else file_storage,
                self.bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )
            return key
        except ClientError as exc:
            raise StorageError(f"S3 upload failed: {exc}") from exc

    def delete(self, key: str):
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except ClientError as exc:
            raise StorageError(f"S3 deletion failed: {exc}") from exc

    def url_for(self, key: str, expires_in=3600) -> str:
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except ClientError as exc:
            raise StorageError(f"Failed to generate presigned URL: {exc}") from exc


def get_storage(app):
    backend = app.config.get("STORAGE_BACKEND", "local")
    if backend == "s3":
        return S3Storage(
            bucket=app.config["S3_BUCKET"],
            region=app.config.get("S3_REGION", "us-east-1"),
            endpoint=app.config.get("S3_ENDPOINT", ""),
            access_key=app.config["S3_ACCESS_KEY"],
            secret_key=app.config["S3_SECRET_KEY"],
        )
    return LocalStorage(app.config["MEDIA_FOLDER"])