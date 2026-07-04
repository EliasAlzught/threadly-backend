"""
Upload endpoints - رفع الصور إلى MinIO (S3-compatible)
"""
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from minio import Minio
from minio.error import S3Error

from app.core.config import settings
from app.models import User
from app.api.deps import get_current_user

router = APIRouter(prefix="/uploads", tags=["Uploads"])


def get_minio_client() -> Minio:
    """إعداد عميل MinIO"""
    client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_SECURE,
    )
    # تأكد من وجود البكت
    if not client.bucket_exists(settings.MINIO_BUCKET):
        client.make_bucket(settings.MINIO_BUCKET)
        # اجعل البكت public للقراءة
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{settings.MINIO_BUCKET}/*"],
                }
            ],
        }
        import json
        client.set_bucket_policy(settings.MINIO_BUCKET, json.dumps(policy))
    return client


ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """رفع صورة وإرجاع الرابط"""
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, "Only JPEG, PNG, WEBP allowed")

    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(400, "File too large (max 10MB)")

    # اسم فريد
    ext = file.filename.split(".")[-1] if "." in file.filename else "jpg"
    object_name = f"{current_user.id}/{uuid.uuid4()}.{ext}"

    try:
        from io import BytesIO
        client = get_minio_client()
        client.put_object(
            settings.MINIO_BUCKET,
            object_name,
            BytesIO(contents),
            length=len(contents),
            content_type=file.content_type,
        )

        # رابط مباشر
        protocol = "https" if settings.MINIO_SECURE else "http"
        url = f"{protocol}://{settings.MINIO_ENDPOINT}/{settings.MINIO_BUCKET}/{object_name}"
        return {"url": url, "object_name": object_name}
    except S3Error as e:
        raise HTTPException(500, f"Upload failed: {e}")
