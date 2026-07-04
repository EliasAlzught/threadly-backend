"""
Notifications endpoints - قراءة وإدارة الإشعارات + تسجيل رمز FCM.

الإشعارات اللحظية تصل عبر نفس WebSocket المستخدم للشات (/api/chat/ws)
برسائل من نوع {"type": "notification", ...}. هذه المسارات للسجل الدائم
وإدارة حالة القراءة.

المسارات:
- GET    /notifications              قائمة الإشعارات + عدد غير المقروء
- GET    /notifications/unread-count عدد غير المقروء فقط
- POST   /notifications/{id}/read    تعليم إشعار كمقروء
- POST   /notifications/read-all     تعليم الكل كمقروء
- DELETE /notifications/{id}         حذف إشعار
- POST   /notifications/fcm-token    تسجيل/تحديث رمز جهاز FCM للـ Push
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Notification, User
from app.schemas import NotificationListOut, NotificationOut, FcmTokenRequest
from app.api.deps import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListOut)
def list_notifications(
    unread_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """قائمة إشعارات المستخدم (الأحدث أولاً) مع عدد غير المقروء."""
    base = db.query(Notification).filter(Notification.user_id == current_user.id)

    unread_count = base.filter(Notification.is_read == False).count()  # noqa: E712

    q = base
    if unread_only:
        q = q.filter(Notification.is_read == False)  # noqa: E712

    items = (
        q.order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"items": items, "unread_count": unread_count}


@router.get("/unread-count")
def unread_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """عدد الإشعارات غير المقروءة - مفيد لشارة العدّاد (badge)."""
    count = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,  # noqa: E712
    ).count()
    return {"unread_count": count}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """تعليم إشعار واحد كمقروء."""
    n = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if not n:
        raise HTTPException(404, "Notification not found")
    n.is_read = True
    db.commit()
    db.refresh(n)
    return n


@router.post("/read-all")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """تعليم كل الإشعارات كمقروءة."""
    updated = db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.is_read == False,  # noqa: E712
    ).update({"is_read": True})
    db.commit()
    return {"marked_read": updated}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """حذف إشعار."""
    n = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if not n:
        raise HTTPException(404, "Notification not found")
    db.delete(n)
    db.commit()


@router.post("/fcm-token")
def register_fcm_token(
    data: FcmTokenRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    تسجيل/تحديث رمز جهاز FCM لاستقبال Push notifications.
    يرسله الـ Flutter بعد الحصول على التوكن من Firebase.
    """
    current_user.fcm_token = data.fcm_token
    db.commit()
    return {"status": "ok"}
