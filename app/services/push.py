"""
إرسال Push Notifications عبر Firebase Cloud Messaging (FCM).

تصميم دفاعي:
- التهيئة كسولة (lazy) ومرة واحدة فقط.
- لو firebase_admin غير مثبّت أو المفتاح غير مضبوط، نعطّل الميزة بهدوء
  ولا نرمي أخطاء (التطبيق يعمل بدون Push في بيئة التطوير).
- FCM يتطلب أن تكون كل قيم data نصوصاً (strings).
"""
from __future__ import annotations

import logging
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("threadly.push")

_initialized = False
_enabled = False
_messaging = None


def _init() -> None:
    global _initialized, _enabled, _messaging
    if _initialized:
        return
    _initialized = True

    if not settings.FIREBASE_CREDENTIALS_PATH:
        logger.info("FCM disabled: FIREBASE_CREDENTIALS_PATH not set")
        return

    try:
        import firebase_admin
        from firebase_admin import credentials, messaging

        if not firebase_admin._apps:
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)
        _messaging = messaging
        _enabled = True
        logger.info("FCM initialized")
    except Exception as e:
        logger.warning("FCM init failed, push disabled: %s", e)


def send_push(
    token: str,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> bool:
    """
    يرسل إشعار Push لجهاز واحد. يرجع True عند النجاح.
    آمن: يرجع False بدل رمي استثناء عند أي مشكلة.
    """
    _init()
    if not _enabled or not _messaging or not token:
        return False

    try:
        # FCM يتطلب قيم data نصية
        str_data = {str(k): str(v) for k, v in (data or {}).items()}
        msg = _messaging.Message(
            token=token,
            notification=_messaging.Notification(title=title, body=body),
            data=str_data,
        )
        _messaging.send(msg)
        return True
    except Exception as e:
        logger.debug("send_push failed: %s", e)
        return False
