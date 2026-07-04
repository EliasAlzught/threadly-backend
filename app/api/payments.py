"""
Payments endpoints - وسائل الدفع والـ checkout

⚠️ ملاحظات أمان حرجة (money movement):
1. idempotency_key يمنع الدفع المزدوج - لو وصل نفس المفتاح مرتين،
   نرجع نفس النتيجة بدون إنشاء معاملة جديدة.
2. لا نخزّن رقم البطاقة الكامل - فقط آخر 4 أرقام.
3. الدفع الحالي "وهمي" (mock) - ينجح دائماً للتطوير.
   نقطة الربط مع Stripe معلّمة بوضوح (_process_payment).
4. كل معاملة لها سجل Transaction مستقل للتدقيق.

الميزات:
- GET    /payments/methods          وسائل الدفع المحفوظة
- POST   /payments/methods          إضافة وسيلة دفع
- DELETE /payments/methods/{id}     حذف وسيلة
- POST   /payments/checkout         دفع (منتج واحد أو طقم) - idempotent
- GET    /payments/transactions     سجل المعاملات
"""
import uuid
from datetime import datetime, date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    PaymentMethod, Transaction, Order, Product, User, RentalBooking,
    PaymentMethodType, PaymentStatus, OrderStatus, OrderType, NotificationType,
)
from app.schemas import (
    PaymentMethodCreate, PaymentMethodOut, CheckoutRequest,
    CheckoutResponse, TransactionOut, OrderOut,
)
from app.api.deps import get_current_user
from app.services.notifications import notify

router = APIRouter(prefix="/payments", tags=["Payments"])

PLATFORM_FEE_RATE = 0.10  # عمولة المنصة 10%


# ============ وسائل الدفع ============

def _method_to_out(m: PaymentMethod) -> dict:
    return {
        "id": m.id,
        "type": m.type.value,
        "label": m.label,
        "card_brand": m.card_brand,
        "card_last4": m.card_last4,
        "card_exp_month": m.card_exp_month,
        "card_exp_year": m.card_exp_year,
        "is_default": m.is_default,
        "created_at": m.created_at,
    }


@router.get("/methods", response_model=list[PaymentMethodOut])
def list_payment_methods(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """وسائل الدفع المحفوظة للمستخدم"""
    methods = db.query(PaymentMethod).filter(
        PaymentMethod.user_id == current_user.id
    ).order_by(PaymentMethod.is_default.desc(), PaymentMethod.created_at.desc()).all()
    return [_method_to_out(m) for m in methods]


@router.post("/methods", response_model=PaymentMethodOut, status_code=201)
def add_payment_method(
    data: PaymentMethodCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    إضافة وسيلة دفع.
    ملاحظة: للبطاقة، الـ Flutter يرسل آخر 4 أرقام فقط - الرقم الكامل
    لا يمر عبر سيرفرنا إطلاقاً (يُعالج ببوابة الدفع مباشرة).
    """
    valid_types = {t.value for t in PaymentMethodType}
    if data.type not in valid_types:
        raise HTTPException(400, f"Invalid type. Must be one of: {valid_types}")

    # لو وسيلة افتراضية جديدة - نلغي الافتراضية القديمة
    if data.is_default:
        db.query(PaymentMethod).filter(
            PaymentMethod.user_id == current_user.id,
            PaymentMethod.is_default == True,
        ).update({"is_default": False})

    method = PaymentMethod(
        user_id=current_user.id,
        type=data.type,
        label=data.label,
        card_brand=data.card_brand,
        card_last4=data.card_last4,
        card_exp_month=data.card_exp_month,
        card_exp_year=data.card_exp_year,
        provider_token=data.provider_token,
        is_default=data.is_default,
    )
    db.add(method)
    db.commit()
    db.refresh(method)
    return _method_to_out(method)


@router.delete("/methods/{method_id}", status_code=204)
def delete_payment_method(
    method_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """حذف وسيلة دفع"""
    method = db.query(PaymentMethod).filter(
        PaymentMethod.id == method_id,
        PaymentMethod.user_id == current_user.id,
    ).first()
    if not method:
        raise HTTPException(404, "Payment method not found")
    db.delete(method)
    db.commit()


# ============ معالجة الدفع ============

def _process_payment(amount: float, method_type: str) -> dict:
    """
    معالجة الدفع الفعلية.

    🔌 نقطة الربط مع بوابة دفع حقيقية:
    حالياً "وهمي" - ينجح دائماً. لربط Stripe لاحقاً، استبدل محتوى
    هذه الدالة باستدعاء Stripe PaymentIntent، وأرجع نفس الشكل:
      { "success": bool, "provider_transaction_id": str, "failure_reason": str|None }

    cash_on_delivery: ما فيه دفع فوري - الحالة pending حتى التسليم.
    """
    if method_type == PaymentMethodType.CASH_ON_DELIVERY.value:
        return {
            "success": True,
            "provider_transaction_id": f"cod_{uuid.uuid4().hex[:12]}",
            "failure_reason": None,
            "deferred": True,  # الدفع مؤجل للتسليم
        }

    # --- محاكاة دفع ناجح (استبدلها بـ Stripe) ---
    return {
        "success": True,
        "provider_transaction_id": f"mock_{uuid.uuid4().hex[:12]}",
        "failure_reason": None,
        "deferred": False,
    }


def _generate_order_number() -> str:
    """رقم طلب فريد قابل للقراءة"""
    return f"THR-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


@router.post("/checkout", response_model=CheckoutResponse)
def checkout(
    data: CheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    دفع موحّد - يدعم منتج واحد أو طقم كامل (عدة منتجات).

    التسلسل الآمن:
    1. فحص idempotency_key - لو موجود، نرجع النتيجة السابقة (لا دفع مزدوج)
    2. التحقق من المنتجات وحساب المجموع
    3. إنشاء Transaction بحالة pending
    4. معالجة الدفع
    5. عند النجاح: إنشاء Orders + تحديث حالة Transaction
    6. عند الفشل: Transaction = failed، لا Orders
    """
    # ===== 1. فحص الـ idempotency =====
    existing_tx = db.query(Transaction).filter(
        Transaction.idempotency_key == data.idempotency_key
    ).first()

    if existing_tx:
        # نفس الطلب وصل مرتين - نرجع النتيجة السابقة بدون دفع جديد
        orders = db.query(Order).filter(
            Order.transaction.has(id=existing_tx.id)
        ).all() if existing_tx.status == PaymentStatus.SUCCEEDED else []
        return {
            "success": existing_tx.status == PaymentStatus.SUCCEEDED,
            "transaction": _transaction_to_out(existing_tx),
            "orders": [_order_to_out(o) for o in orders],
            "message": "Already processed (idempotent response)",
        }

    # ===== 2. التحقق من المنتجات =====
    if not data.product_ids:
        raise HTTPException(400, "No products provided")

    products = db.query(Product).filter(
        Product.id.in_(data.product_ids)
    ).all()

    if len(products) != len(data.product_ids):
        raise HTTPException(404, "One or more products not found")

    for p in products:
        if not p.is_available:
            raise HTTPException(400, f"Product '{p.title}' is no longer available")
        if p.seller_id == current_user.id:
            raise HTTPException(400, "You cannot buy your own product")

    is_rental = data.order_type == "rental"

    # حساب المجموع
    subtotal = 0.0
    rental_days = 0
    if is_rental:
        if not data.rent_start or not data.rent_end:
            raise HTTPException(400, "Rental dates required for rental order")
        rental_days = (data.rent_end - data.rent_start).days
        if rental_days < 1:
            raise HTTPException(400, "Rental must be at least 1 day")
        for p in products:
            if not p.rental_price_per_day:
                raise HTTPException(400, f"Product '{p.title}' is not available for rent")
            subtotal += p.rental_price_per_day * rental_days
    else:
        subtotal = sum(p.sale_price for p in products)

    platform_fee = round(subtotal * PLATFORM_FEE_RATE, 2)
    total = round(subtotal + platform_fee, 2)

    # ===== 3. إنشاء Transaction (pending) =====
    method_type = data.payment_method_type
    valid_types = {t.value for t in PaymentMethodType}
    if method_type not in valid_types:
        raise HTTPException(400, f"Invalid payment method type")

    transaction = Transaction(
        user_id=current_user.id,
        amount=total,
        currency="USD",
        method_type=method_type,
        status=PaymentStatus.PROCESSING,
        idempotency_key=data.idempotency_key,
    )
    db.add(transaction)
    db.flush()  # نحصل على transaction.id بدون commit نهائي

    # ===== 4. معالجة الدفع =====
    try:
        result = _process_payment(total, method_type)
    except Exception as e:
        transaction.status = PaymentStatus.FAILED
        transaction.failure_reason = str(e)
        db.commit()
        raise HTTPException(502, f"Payment processing error: {e}")

    if not result["success"]:
        transaction.status = PaymentStatus.FAILED
        transaction.failure_reason = result.get("failure_reason", "Payment declined")
        db.commit()
        return {
            "success": False,
            "transaction": _transaction_to_out(transaction),
            "orders": [],
            "message": transaction.failure_reason,
        }

    # ===== 5. النجاح - إنشاء Orders =====
    transaction.provider_transaction_id = result["provider_transaction_id"]
    is_deferred = result.get("deferred", False)

    # cash on delivery: الحالة pending حتى التسليم
    transaction.status = (
        PaymentStatus.PENDING if is_deferred else PaymentStatus.SUCCEEDED
    )
    if not is_deferred:
        transaction.completed_at = datetime.utcnow()

    created_orders = []
    for p in products:
        # سعر هذا المنتج
        if is_rental:
            item_subtotal = p.rental_price_per_day * rental_days
        else:
            item_subtotal = p.sale_price
        item_fee = round(item_subtotal * PLATFORM_FEE_RATE, 2)

        order = Order(
            order_number=_generate_order_number(),
            buyer_id=current_user.id,
            seller_id=p.seller_id,
            product_id=p.id,
            order_type=OrderType.RENTAL if is_rental else OrderType.PURCHASE,
            status=OrderStatus.CONFIRMED if not is_deferred else OrderStatus.PENDING,
            subtotal=item_subtotal,
            platform_fee=item_fee,
            total=round(item_subtotal + item_fee, 2),
            shipping_address=data.shipping_address,
            paid_at=datetime.utcnow() if not is_deferred else None,
        )
        db.add(order)
        db.flush()

        # ربط الطلب بالمعاملة
        order.transaction = transaction

        # حجز إيجار لو إيجار
        if is_rental:
            booking = RentalBooking(
                product_id=p.id,
                order_id=order.id,
                rent_start=data.rent_start,
                rent_end=data.rent_end,
            )
            db.add(booking)
            # المنتج المؤجّر يصير غير متاح
            p.is_available = False
        else:
            # المنتج المُباع يصير غير متاح
            p.is_available = False

        created_orders.append(order)

    db.commit()
    for o in created_orders:
        db.refresh(o)
    db.refresh(transaction)

    # ===== إشعارات بعد نجاح الدفع =====
    pay_label = "Order placed - pay on delivery" if is_deferred else "Payment received"
    # إشعار لكل بائع بطلبه الجديد
    for o in created_orders:
        prod = next((p for p in products if p.id == o.product_id), None)
        title = prod.title if prod else "your item"
        notify(
            db, o.seller_id,
            type=NotificationType.NEW_ORDER,
            title="New order received 🛍️",
            message=f'You have a new order for "{title}" (#{o.order_number}).',
            data={
                "order_id": str(o.id),
                "order_number": o.order_number,
                "product_id": str(o.product_id),
            },
        )
    # إشعار واحد للمشتري يلخّص العملية
    notify(
        db, current_user.id,
        type=NotificationType.ORDER_PLACED,
        title="Order confirmed ✅",
        message=(
            f"{pay_label}. {len(created_orders)} item(s), total {transaction.amount} "
            f"{transaction.currency}."
        ),
        data={
            "transaction_id": str(transaction.id),
            "order_ids": [str(o.id) for o in created_orders],
        },
    )

    return {
        "success": True,
        "transaction": _transaction_to_out(transaction),
        "orders": [_order_to_out(o) for o in created_orders],
        "message": (
            "Order placed - pay on delivery" if is_deferred
            else "Payment successful"
        ),
    }


# ============ سجل المعاملات ============

@router.get("/transactions", response_model=list[TransactionOut])
def list_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """سجل المعاملات المالية للمستخدم"""
    txs = db.query(Transaction).filter(
        Transaction.user_id == current_user.id
    ).order_by(Transaction.created_at.desc()).all()
    return [_transaction_to_out(t) for t in txs]


# ============ Helpers ============

def _transaction_to_out(t: Transaction) -> dict:
    return {
        "id": t.id,
        "amount": t.amount,
        "currency": t.currency,
        "method_type": t.method_type.value,
        "status": t.status.value,
        "order_id": t.order.id if t.order else None,
        "provider_transaction_id": t.provider_transaction_id,
        "failure_reason": t.failure_reason,
        "created_at": t.created_at,
        "completed_at": t.completed_at,
    }


def _order_to_out(o: Order) -> dict:
    return {
        "id": o.id,
        "order_number": o.order_number,
        "order_type": o.order_type.value,
        "status": o.status.value,
        "subtotal": o.subtotal,
        "platform_fee": o.platform_fee,
        "total": o.total,
        "product_id": o.product_id,
        "buyer_id": o.buyer_id,
        "seller_id": o.seller_id,
        "tracking_number": o.tracking_number,
        "paid_at": o.paid_at,
        "created_at": o.created_at,
    }
