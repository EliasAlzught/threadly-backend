"""
Merchant endpoints - تفعيل وضع التاجر والاشتراكات.

المسارات:
- GET  /merchant/status      حالة التاجر/الاشتراك (للواجهة)
- POST /merchant/free-trial  بدء فترة تجريبية مجانية (لو مفعّلة من الأدمن)
- POST /merchant/subscribe   اشتراك شهري مدفوع (شهر كامل) - idempotent
- POST /merchant/cancel      إلغاء التجديد (يبقى سارياً حتى نهاية المدة)

ملاحظة الدفع: نسجّل Transaction لكل اشتراك مدفوع (تدقيق + منع خصم مزدوج
عبر idempotency_key). معالجة الدفع حالياً وهمية (mock) مع نقطة ربط واضحة
لـ Stripe - نفس نمط payments.py.
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    User, Transaction, PaymentMethodType, PaymentStatus, NotificationType,
)
from app.schemas import SubscriptionStatusOut, SubscribeRequest
from app.api.deps import get_current_user
from app.services import subscriptions as subs
from app.services.notifications import notify

router = APIRouter(prefix="/merchant", tags=["Merchant"])


@router.get("/status", response_model=SubscriptionStatusOut)
def get_merchant_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """حالة التاجر والاشتراك الحالية."""
    return subs.subscription_status(db, current_user)


@router.post("/free-trial", response_model=SubscriptionStatusOut)
def start_free_trial(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    بدء الفترة التجريبية المجانية ليصبح المستخدم تاجراً.
    متاح فقط حين يفعّل الأدمن الفترة التجريبية ولم يستخدمها المستخدم من قبل.
    """
    ps = subs.get_platform_settings(db)

    # عنده اشتراك ساري؟ لا حاجة لتجربة - نرجع الحالة كما هي.
    if subs.get_active_subscription(db, current_user):
        return subs.subscription_status(db, current_user)

    if not ps.free_trial_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Free trial is currently disabled. Please subscribe.",
                "needs_subscription": True,
            },
        )

    if subs.has_used_trial(db, current_user):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "You have already used your free trial. Please subscribe.",
                "needs_subscription": True,
            },
        )

    sub = subs.start_free_trial(db, current_user)

    notify(
        db, current_user.id,
        type=NotificationType.SUBSCRIPTION,
        title="Free trial activated 🎉",
        message=f"You're now a merchant! Your free trial lasts {ps.free_trial_days} days.",
        data={"subscription_id": str(sub.id), "is_trial": True},
    )
    return subs.subscription_status(db, current_user)


def _charge(amount: float, method_type: str) -> dict:
    """
    🔌 نقطة ربط الدفع الحقيقي (Stripe).
    حالياً وهمي - ينجح دائماً. استبدل المحتوى باستدعاء Stripe وأرجع نفس الشكل.
    """
    return {
        "success": True,
        "provider_transaction_id": f"sub_{uuid.uuid4().hex[:12]}",
        "failure_reason": None,
    }


@router.post("/subscribe", response_model=SubscriptionStatusOut)
def subscribe_monthly(
    data: SubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    اشتراك شهري مدفوع - يمنح شهراً كاملاً (وليس مجرد بقية تجربة).
    idempotent عبر idempotency_key.
    """
    ps = subs.get_platform_settings(db)
    amount = ps.monthly_price

    # ===== منع الخصم المزدوج =====
    existing_tx = db.query(Transaction).filter(
        Transaction.idempotency_key == data.idempotency_key
    ).first()
    if existing_tx:
        # نفس الطلب وصل مرتين - لا نخصم/نمدّد مجدداً، نرجع الحالة الحالية.
        return subs.subscription_status(db, current_user)

    # ===== تحقق من وسيلة الدفع =====
    valid_types = {t.value for t in PaymentMethodType}
    if data.payment_method_type not in valid_types:
        raise HTTPException(400, "Invalid payment method type")
    # الدفع عند الاستلام لا يصلح لاشتراك رقمي فوري
    if data.payment_method_type == PaymentMethodType.CASH_ON_DELIVERY.value:
        raise HTTPException(400, "Cash on delivery is not supported for subscriptions")

    # ===== سجل معاملة (PROCESSING) =====
    tx = Transaction(
        user_id=current_user.id,
        amount=amount,
        currency=ps.currency,
        method_type=data.payment_method_type,
        status=PaymentStatus.PROCESSING,
        idempotency_key=data.idempotency_key,
    )
    db.add(tx)
    db.flush()

    # ===== معالجة الدفع =====
    try:
        result = _charge(amount, data.payment_method_type)
    except Exception as e:
        tx.status = PaymentStatus.FAILED
        tx.failure_reason = str(e)
        db.commit()
        raise HTTPException(502, f"Payment processing error: {e}")

    if not result["success"]:
        tx.status = PaymentStatus.FAILED
        tx.failure_reason = result.get("failure_reason", "Payment declined")
        db.commit()
        raise HTTPException(402, tx.failure_reason)

    tx.status = PaymentStatus.SUCCEEDED
    tx.provider_transaction_id = result["provider_transaction_id"]
    tx.completed_at = datetime.utcnow()
    db.commit()

    # ===== تفعيل/تمديد الاشتراك (شهر كامل) =====
    sub = subs.start_or_extend_monthly(
        db, current_user,
        amount_paid=amount,
        transaction_id=tx.id,
        auto_renew=data.auto_renew,
    )

    notify(
        db, current_user.id,
        type=NotificationType.SUBSCRIPTION,
        title="Subscription active ✅",
        message="Your monthly merchant subscription is active. You can list products now.",
        data={"subscription_id": str(sub.id), "expires_at": sub.expires_at.isoformat()},
    )
    return subs.subscription_status(db, current_user)


@router.post("/cancel", response_model=SubscriptionStatusOut)
def cancel_subscription(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    إلغاء التجديد التلقائي. الاشتراك يبقى سارياً حتى نهاية المدة المدفوعة.
    """
    sub = subs.cancel_subscription(db, current_user)
    if not sub:
        raise HTTPException(404, "No active subscription to cancel")

    notify(
        db, current_user.id,
        type=NotificationType.SUBSCRIPTION,
        title="Subscription cancelled",
        message=f"Auto-renew is off. You keep merchant access until {sub.expires_at.date()}.",
        data={"subscription_id": str(sub.id), "expires_at": sub.expires_at.isoformat()},
    )
    return subs.subscription_status(db, current_user)
