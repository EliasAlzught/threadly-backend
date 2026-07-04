"""
خدمة الإشعارات - المكان الموحّد لإنشاء أي إشعار.

كل إشعار يمرّ من هنا فيحصل على:
1. صف دائم في جدول notifications (يظهر في قائمة الإشعارات لاحقاً).
2. دفعة لحظية عبر WebSocket لو المستخدم متصل (يظهر فوراً).
3. دفعة Push عبر FCM (best-effort) لو عنده fcm_token ومُهيّأ Firebase.

قاعدة مهمة: الإشعارات ثانوية - أي فشل فيها (socket/FCM) يجب ألا يُفشل
العملية الأساسية (إرسال رسالة، إنشاء طلب...). لذلك كل الإرسال اللحظي
مغلّف بـ try/except صامت.

الاستدعاء متزامن (sync) ليناسب نقاط النهاية المتزامنة. يُفضّل استدعاؤه
بعد commit الأساسي حتى تكون البيانات التي يشير إليها الإشعار دائمة.
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Notification, NotificationType, User

logger = logging.getLogger("threadly.notifications")


def notify(
    db: Session,
    user_id: UUID | str,
    *,
    type: NotificationType | str,
    title: str,
    message: str,
    data: Optional[dict] = None,
    push: bool = True,
) -> Notification:
    """
    ينشئ إشعاراً واحداً، يحفظه، ثم يدفعه لحظياً.

    - user_id: المستلم.
    - type: نوع الإشعار (NotificationType).
    - data: حمولة إضافية للـ Flutter (مثلاً thread_id / order_id) للتنقّل.
    """
    type_value = type.value if isinstance(type, NotificationType) else str(type)

    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        type=type_value,
        data=data or {},
        is_read=False,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    if push:
        _push_realtime(notification)
        _push_fcm(db, notification)

    return notification


def _notification_payload(n: Notification) -> dict:
    return {
        "type": "notification",
        "notification": {
            "id": str(n.id),
            "title": n.title,
            "message": n.message,
            "notification_type": n.type,
            "data": n.data or {},
            "is_read": n.is_read,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        },
    }


def _push_realtime(n: Notification) -> None:
    """دفعة WebSocket لحظية - صامتة عند الفشل."""
    try:
        # استيراد متأخر لتفادي الاستيراد الدائري
        from app.services.realtime import manager
        manager.dispatch(str(n.user_id), _notification_payload(n))
    except Exception as e:  # pragma: no cover - best effort
        logger.debug("realtime push failed: %s", e)


def _push_fcm(db: Session, n: Notification) -> None:
    """
    دفعة Push عبر Firebase Cloud Messaging - best effort.
    تعمل فقط لو:
    - المستخدم عنده fcm_token.
    - Firebase مُهيّأ (FIREBASE_CREDENTIALS_PATH مضبوط و firebase_admin مثبّت).
    أي خطأ يُتجاهل بهدوء حتى لا يؤثر على العملية الأساسية.
    """
    try:
        user = db.query(User).filter(User.id == n.user_id).first()
        if not user or not user.fcm_token:
            return

        from app.services.push import send_push  # استيراد متأخر
        send_push(
            token=user.fcm_token,
            title=n.title,
            body=n.message,
            data={"notification_type": n.type, **(n.data or {})},
        )
    except Exception as e:  # pragma: no cover - best effort
        logger.debug("FCM push skipped/failed: %s", e)
