"""
تهيئة قاعدة البيانات عند الإقلاع.

لماذا هذا الملف؟
المشروع يستخدم Base.metadata.create_all الذي ينشئ الجداول الجديدة فقط،
لكنه لا يضيف أعمدة جديدة لجداول موجودة مسبقاً. لذلك نضيف الأعمدة الجديدة
على users (is_merchant, is_admin) يدوياً بشكل آمن (idempotent) باستخدام
ADD COLUMN IF NOT EXISTS، ثم:
- نضمن وجود صف إعدادات المنصة (singleton).
- نمنح صلاحية الأدمن للإيميلات في ADMIN_EMAILS.

كل العمليات آمنة للتكرار - يمكن تشغيلها عند كل إقلاع بدون ضرر.

ملاحظة: في الإنتاج يُفضّل استخدام Alembic للهجرات، لكن هذا يبقي تجربة
"التشغيل بأمر واحد" الحالية تعمل دون خطوات إضافية.
"""
import logging

from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine, SessionLocal
from app.models import User

logger = logging.getLogger("threadly.bootstrap")


# أعمدة جديدة على جداول موجودة: (اسم الجدول, تعريف العمود)
_NEW_COLUMNS = [
    ("users", "is_merchant BOOLEAN NOT NULL DEFAULT false"),
    ("users", "is_admin BOOLEAN NOT NULL DEFAULT false"),
]


def _add_missing_columns() -> None:
    """يضيف الأعمدة الجديدة على الجداول الموجودة (آمن للتكرار)."""
    with engine.begin() as conn:
        for table, column_def in _NEW_COLUMNS:
            try:
                conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column_def}")
                )
            except Exception as e:
                # لا نوقف الإقلاع - نسجّل فقط (مثلاً قواعد لا تدعم IF NOT EXISTS)
                logger.warning("Could not add column on %s (%s): %s", table, column_def, e)


def _ensure_platform_settings() -> None:
    """ينشئ صف إعدادات المنصة لو لم يوجد."""
    from app.services.subscriptions import get_platform_settings

    db = SessionLocal()
    try:
        get_platform_settings(db)  # ينشئه بالقيم الافتراضية لو غير موجود
    finally:
        db.close()


def _bootstrap_admins() -> None:
    """يمنح صلاحية الأدمن للإيميلات المحددة في ADMIN_EMAILS."""
    emails = [e.strip().lower() for e in settings.ADMIN_EMAILS if e.strip()]
    if not emails:
        return

    db = SessionLocal()
    try:
        promoted = 0
        for email in emails:
            user = db.query(User).filter(User.email == email).first()
            if user and not user.is_admin:
                user.is_admin = True
                promoted += 1
        if promoted:
            db.commit()
            logger.info("Granted admin to %d user(s)", promoted)
    finally:
        db.close()


def bootstrap_database() -> None:
    """يُستدعى مرة واحدة عند إقلاع التطبيق."""
    _add_missing_columns()
    _ensure_platform_settings()
    _bootstrap_admins()
