"""
Orders endpoints - شراء وإيجار
"""
import uuid
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Order, Product, RentalBooking, User, OrderStatus, OrderType, NotificationType
from app.schemas import OrderCreate, OrderOut
from app.api.deps import get_current_user
from app.services.notifications import notify

router = APIRouter(prefix="/orders", tags=["Orders"])

PLATFORM_FEE_PERCENT = 0.10  # 10% عمولة المنصة


def _generate_order_number() -> str:
    return f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"


def _check_rental_availability(
    db: Session,
    product_id: UUID,
    rent_start,
    rent_end,
) -> bool:
    """التحقق من عدم تعارض الإيجار مع حجوزات أخرى"""
    conflicts = db.query(RentalBooking).filter(
        and_(
            RentalBooking.product_id == product_id,
            # التعارض: الحجز الجديد يتقاطع مع حجز موجود
            or_(
                and_(
                    RentalBooking.rent_start <= rent_start,
                    RentalBooking.rent_end >= rent_start,
                ),
                and_(
                    RentalBooking.rent_start <= rent_end,
                    RentalBooking.rent_end >= rent_end,
                ),
                and_(
                    RentalBooking.rent_start >= rent_start,
                    RentalBooking.rent_end <= rent_end,
                ),
            ),
        )
    ).first()
    return conflicts is None


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    data: OrderCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """إنشاء طلب جديد (شراء أو إيجار)"""
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(404, "Product not found")

    if product.seller_id == current_user.id:
        raise HTTPException(400, "Cannot order your own product")

    if not product.is_available:
        raise HTTPException(400, "Product not available")

    # حساب السعر
    if data.order_type == "rental":
        if not data.rent_start or not data.rent_end:
            raise HTTPException(400, "Rental dates required")
        if not product.rental_price_per_day:
            raise HTTPException(400, "Product not available for rental")

        # تحقق من عدم تعارض التواريخ
        if not _check_rental_availability(
            db, product.id, data.rent_start, data.rent_end
        ):
            raise HTTPException(
                409,
                "Product is already booked for these dates"
            )

        days = (data.rent_end - data.rent_start).days + 1
        subtotal = product.rental_price_per_day * days
    else:
        if not product.sale_price:
            raise HTTPException(400, "Product not available for sale")
        subtotal = product.sale_price

    platform_fee = subtotal * PLATFORM_FEE_PERCENT
    total = subtotal + platform_fee

    # إنشاء الطلب
    order = Order(
        order_number=_generate_order_number(),
        buyer_id=current_user.id,
        seller_id=product.seller_id,
        product_id=product.id,
        order_type=OrderType(data.order_type),
        status=OrderStatus.PENDING,
        subtotal=subtotal,
        platform_fee=platform_fee,
        total=total,
        shipping_address=data.shipping_address,
    )
    db.add(order)
    db.flush()

    # لو إيجار، اعمل booking
    if data.order_type == "rental":
        booking = RentalBooking(
            product_id=product.id,
            order_id=order.id,
            rent_start=data.rent_start,
            rent_end=data.rent_end,
        )
        db.add(booking)

    db.commit()
    db.refresh(order)

    # إشعار للبائع: طلب جديد
    notify(
        db, product.seller_id,
        type=NotificationType.NEW_ORDER,
        title="New order received 🛍️",
        message=f'You have a new order for "{product.title}" (#{order.order_number}).',
        data={
            "order_id": str(order.id),
            "order_number": order.order_number,
            "product_id": str(product.id),
        },
    )
    # إشعار للمشتري: تأكيد تسجيل الطلب
    notify(
        db, current_user.id,
        type=NotificationType.ORDER_PLACED,
        title="Order placed ✅",
        message=f'Your order #{order.order_number} has been placed.',
        data={"order_id": str(order.id), "order_number": order.order_number},
    )

    return OrderOut.model_validate(order)


@router.get("/me", response_model=list[OrderOut])
def get_my_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """طلباتي (كمشتري)"""
    orders = db.query(Order).filter(
        Order.buyer_id == current_user.id
    ).order_by(Order.created_at.desc()).all()
    return orders


@router.get("/sales", response_model=list[OrderOut])
def get_my_sales(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """مبيعاتي (كبائع)"""
    orders = db.query(Order).filter(
        Order.seller_id == current_user.id
    ).order_by(Order.created_at.desc()).all()
    return orders


@router.get("/{order_id}", response_model=OrderOut)
def get_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """تفاصيل طلب"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        raise HTTPException(403, "Not authorized")
    return order


@router.post("/{order_id}/confirm")
def confirm_order(
    order_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """البائع يأكد الطلب"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.seller_id != current_user.id:
        raise HTTPException(403, "Not your sale")

    order.status = OrderStatus.CONFIRMED
    db.commit()

    # إشعار للمشتري بتأكيد الطلب
    notify(
        db, order.buyer_id,
        type=NotificationType.ORDER_STATUS,
        title="Order confirmed 📦",
        message=f"Your order #{order.order_number} was confirmed by the seller.",
        data={
            "order_id": str(order.id),
            "order_number": order.order_number,
            "status": OrderStatus.CONFIRMED.value,
        },
    )
    return {"status": "confirmed"}


@router.post("/{order_id}/ship")
def ship_order(
    order_id: UUID,
    tracking_number: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """البائع يحدث الطلب لـ shipped"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    if order.seller_id != current_user.id:
        raise HTTPException(403, "Not your sale")

    order.status = OrderStatus.SHIPPED
    order.tracking_number = tracking_number
    db.commit()

    # إشعار للمشتري بالشحن + رقم التتبّع
    notify(
        db, order.buyer_id,
        type=NotificationType.ORDER_STATUS,
        title="Order shipped 🚚",
        message=f"Your order #{order.order_number} has shipped. Tracking: {tracking_number}.",
        data={
            "order_id": str(order.id),
            "order_number": order.order_number,
            "status": OrderStatus.SHIPPED.value,
            "tracking_number": tracking_number,
        },
    )
    return {"status": "shipped"}
