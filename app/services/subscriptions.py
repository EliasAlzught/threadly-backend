"""
منطق الاشتراكات والتاجر - المصدر الوحيد للحقيقة لقدرة المستخدم على البيع.

القواعد (سليمة ومتسقة):
1. القدرة على نشر المنتجات = وجود اشتراك status=active و expires_at في المستقبل.
2. الفترة التجريبية المجانية:
   - يتحكم بها الأدمن عبر PlatformSetting.free_trial_enabled.
   - عند تشغيلها: أي مستخدم لم يستخدم تجربته من قبل يقدر يصير تاجراً مجاناً.
   - مدتها free_trial_days.
   - تجربة واحدة لكل مستخدم (منعاً للاستغلال).
3. الاشتراك الشهري المدفوع:
   - يمنح "شهراً كاملاً" (monthly_period_days) وليس مجرد بقية تجربة.
   - لو المستخدم في تجربة وقرر الدفع: نحوّله لشهر كامل من الآن (is_trial=False).
   - لو عنده اشتراك مدفوع ساري وجدّد مبكراً: نمدّد من تاريخ الانتهاء الحالي
     حتى لا يخسر أياماً دفع ثمنها.
4. إيقاف الأدمن للفترة التجريبية لا يقطع التجارب القائمة - تبقى سارية حتى تنتهي.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    PlatformSetting, Subscription, SubscriptionPlan, SubscriptionStatus, User,
)


# ============ إعدادات المنصة (singleton) ============

def get_platform_settings(db: Session) -> PlatformSetting:
    """
    يجلب إعدادات المنصة، وينشئها بالقيم الافتراضية من الـ config لو لم توجد.
    صف واحد ثابت id=1.
    """
    ps = db.query(PlatformSetting).filter(PlatformSetting.id == 1).first()
    if ps is None:
        ps = PlatformSetting(
            id=1,
            free_trial_enabled=settings.DEFAULT_FREE_TRIAL_ENABLED,
            free_trial_days=settings.DEFAULT_FREE_TRIAL_DAYS,
            monthly_price=settings.DEFAULT_MONTHLY_PRICE,
            monthly_period_days=settings.DEFAULT_MONTHLY_PERIOD_DAYS,
            currency=settings.SUBSCRIPTION_CURRENCY,
        )
        db.add(ps)
        db.commit()
        db.refresh(ps)
    return ps


# ============ استعلام الاشتراك ============

def get_active_subscription(db: Session, user: User) -> Optional[Subscription]:
    """
    يرجع الاشتراك الساري للمستخدم أو None.
    يعلّم الاشتراكات المنتهية بـ EXPIRED أثناء المرور (تنظيف كسول).
    """
    now = datetime.utcnow()
    subs = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id)
        .order_by(Subscription.expires_at.desc())
        .all()
    )

    active: Optional[Subscription] = None
    dirty = False
    for s in subs:
        if s.status == SubscriptionStatus.ACTIVE and s.expires_at <= now:
            # انتهت مدته لكن لم تُحدَّث حالته بعد
            s.status = SubscriptionStatus.EXPIRED
            dirty = True
            continue
        if s.status == SubscriptionStatus.ACTIVE and s.expires_at > now and active is None:
            active = s
    if dirty:
        db.commit()
    return active


def has_active_subscription(db: Session, user: User) -> bool:
    return get_active_subscription(db, user) is not None


def has_used_trial(db: Session, user: User) -> bool:
    """هل سبق للمستخدم أن استخدم تجربة مجانية؟ (تجربة واحدة لكل مستخدم)"""
    return (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user.id,
            Subscription.is_trial == True,  # noqa: E712
        )
        .first()
        is not None
    )


def days_left(sub: Optional[Subscription]) -> int:
    if not sub:
        return 0
    delta = sub.expires_at - datetime.utcnow()
    return max(0, delta.days + (1 if delta.seconds > 0 else 0))


# ============ تفعيل / تمديد ============

def start_free_trial(db: Session, user: User) -> Subscription:
    """
    يبدأ فترة تجريبية مجانية.
    الشروط (يجب أن يتحقق منها المستدعي عبر can_start_free_trial أولاً، لكن
    نتحقق هنا أيضاً دفاعياً):
    - الفترة التجريبية مفعّلة من الأدمن.
    - المستخدم ليس لديه اشتراك ساري.
    - المستخدم لم يستخدم تجربته من قبل.
    """
    ps = get_platform_settings(db)
    if not ps.free_trial_enabled:
        raise ValueError("Free trial is currently disabled")

    existing = get_active_subscription(db, user)
    if existing:
        return existing  # عنده اشتراك ساري بالفعل - لا حاجة لتجربة جديدة

    if has_used_trial(db, user):
        raise ValueError("Free trial already used")

    now = datetime.utcnow()
    sub = Subscription(
        user_id=user.id,
        plan=SubscriptionPlan.FREE_TRIAL,
        status=SubscriptionStatus.ACTIVE,
        is_trial=True,
        auto_renew=False,
        started_at=now,
        expires_at=now + timedelta(days=ps.free_trial_days),
        amount_paid=0.0,
    )
    db.add(sub)

    user.is_merchant = True
    db.commit()
    db.refresh(sub)
    return sub


def start_or_extend_monthly(
    db: Session,
    user: User,
    *,
    amount_paid: float,
    transaction_id: Optional[UUID] = None,
    auto_renew: bool = False,
) -> Subscription:
    """
    يفعّل/يجدّد اشتراكاً شهرياً مدفوعاً - شهر كامل دائماً.

    - لو عنده اشتراك مدفوع ساري: نمدّد من تاريخ الانتهاء (لا يخسر أياماً مدفوعة).
    - غير ذلك (تجربة سارية أو لا شيء): شهر كامل من الآن، ونُنهي أي تجربة سارية.
    """
    ps = get_platform_settings(db)
    period = timedelta(days=ps.monthly_period_days)
    now = datetime.utcnow()

    active = get_active_subscription(db, user)

    if active and not active.is_trial and active.plan in (
        SubscriptionPlan.MONTHLY, SubscriptionPlan.YEARLY
    ):
        # تجديد لاشتراك مدفوع ساري - نمدّد من نهايته الحالية
        active.expires_at = max(now, active.expires_at) + period
        active.plan = SubscriptionPlan.MONTHLY
        active.status = SubscriptionStatus.ACTIVE
        active.amount_paid = (active.amount_paid or 0.0) + amount_paid
        active.auto_renew = auto_renew
        if transaction_id:
            active.transaction_id = transaction_id
        user.is_merchant = True
        db.commit()
        db.refresh(active)
        return active

    # تجربة سارية أو لا اشتراك: شهر كامل من الآن
    if active and active.is_trial:
        # ننهي التجربة - الاشتراك المدفوع يحلّ محلها بشهر كامل
        active.status = SubscriptionStatus.EXPIRED

    sub = Subscription(
        user_id=user.id,
        plan=SubscriptionPlan.MONTHLY,
        status=SubscriptionStatus.ACTIVE,
        is_trial=False,
        auto_renew=auto_renew,
        started_at=now,
        expires_at=now + period,
        amount_paid=amount_paid,
        transaction_id=transaction_id,
    )
    db.add(sub)
    user.is_merchant = True
    db.commit()
    db.refresh(sub)
    return sub


def cancel_subscription(db: Session, user: User) -> Optional[Subscription]:
    """
    يلغي التجديد التلقائي ويعلّم الاشتراك CANCELLED، لكنه يبقى سارياً
    (القدرة على النشر مستمرة) حتى expires_at. سلوك متعارف عليه وعادل.
    """
    active = get_active_subscription(db, user)
    if not active:
        return None
    active.status = SubscriptionStatus.CANCELLED
    active.auto_renew = False
    db.commit()
    db.refresh(active)
    return active


# ============ ملخّص للحالة (للـ API) ============

def subscription_status(db: Session, user: User) -> dict:
    """ملخّص شامل لحالة التاجر/الاشتراك - يستهلكه الـ Flutter."""
    ps = get_platform_settings(db)
    active = get_active_subscription(db, user)
    can_trial = (
        ps.free_trial_enabled
        and active is None
        and not has_used_trial(db, user)
    )

    return {
        "is_merchant": user.is_merchant,
        "can_list_products": active is not None,
        "has_active_subscription": active is not None,
        "free_trial_enabled": ps.free_trial_enabled,
        "can_start_free_trial": can_trial,
        "free_trial_days": ps.free_trial_days,
        "monthly_price": ps.monthly_price,
        "monthly_period_days": ps.monthly_period_days,
        "currency": ps.currency,
        "subscription": {
            "id": str(active.id),
            "plan": active.plan.value,
            "status": active.status.value,
            "is_trial": active.is_trial,
            "auto_renew": active.auto_renew,
            "started_at": active.started_at.isoformat(),
            "expires_at": active.expires_at.isoformat(),
            "days_left": days_left(active),
        } if active else None,
    }
