"""
Dependencies للـ API endpoints
"""
from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login/form")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """الحصول على المستخدم الحالي من الـ JWT"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if not payload:
        raise credentials_exception

    user_id: str = payload.get("sub")
    if not user_id:
        raise credentials_exception

    try:
        user = db.query(User).filter(User.id == UUID(user_id)).first()
    except ValueError:
        raise credentials_exception

    if not user or not user.is_active:
        raise credentials_exception

    return user


def require_active_merchant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    """
    يتطلب أن يكون المستخدم تاجراً باشتراك ساري (تجربة مجانية أو مدفوع).
    يُستخدم لحماية نشر/تعديل المنتجات.

    رسالة 402 (Payment Required) تخبر الـ Flutter بتوجيه المستخدم لشاشة
    الاشتراك. الحقل needs_subscription يسهّل التعامل بالواجهة.
    """
    # استيراد متأخر لتفادي الدوران
    from app.services.subscriptions import get_active_subscription

    active = get_active_subscription(db, current_user)
    if active is None:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "An active merchant subscription is required to list products.",
                "needs_subscription": True,
            },
        )
    return current_user


def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """يتطلب صلاحية الأدمن (لإدارة إعدادات المنصة)."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user
