"""
Admin endpoints - إدارة إعدادات المنصة وقت التشغيل.

أهمها: تشغيل/إيقاف الفترة التجريبية المجانية وضبط مدتها وسعر الاشتراك،
كل ذلك دون تعديل الكود أو إعادة النشر.

محمية بـ require_admin (يحتاج user.is_admin = True).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User, PlatformSetting
from app.schemas import PlatformSettingsOut, PlatformSettingsUpdate
from app.api.deps import require_admin
from app.services import subscriptions as subs

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/settings", response_model=PlatformSettingsOut)
def get_settings(
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """قراءة إعدادات المنصة الحالية."""
    return subs.get_platform_settings(db)


@router.put("/settings", response_model=PlatformSettingsOut)
def update_settings(
    data: PlatformSettingsUpdate,
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    تحديث إعدادات المنصة (تحديث جزئي).
    مثال لإيقاف الفترة التجريبية:
        PUT /api/admin/settings  { "free_trial_enabled": false }

    ملاحظة: إيقاف الفترة التجريبية لا يقطع التجارب السارية - تبقى حتى تنتهي.
    """
    ps: PlatformSetting = subs.get_platform_settings(db)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(ps, field, value)

    db.commit()
    db.refresh(ps)
    return ps
