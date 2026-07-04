"""
نماذج قاعدة البيانات - النسخة الموسّعة

التوسعات الجديدة:
1. Product: subcategory + slot للأفاتار + attributes
2. Avatar: شخصية المستخدم القابلة للتخصيص
3. PaymentMethod: وسائل الدفع المحفوظة
4. Transaction: سجل المعاملات المالية
5. Outfit: الأطقم المحفوظة
"""
from datetime import datetime
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, ForeignKey,
    Text, Enum as SAEnum, JSON, Date, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
import uuid

from app.db.session import Base


# ============ ENUMS ============

class ListingType(str, PyEnum):
    SALE = "sale"
    RENTAL = "rental"
    BOTH = "both"


class Condition(str, PyEnum):
    BRAND_NEW = "brand_new"
    LIKE_NEW = "like_new"
    USED = "used"


class OrderStatus(str, PyEnum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    RETURNED = "returned"
    CANCELLED = "cancelled"


class OrderType(str, PyEnum):
    PURCHASE = "purchase"
    RENTAL = "rental"


# ============ ENUMS الجديدة ============

class ProductSlot(str, PyEnum):
    """خانة القطعة على الأفاتار - تحدد وين تُلبس"""
    HEAD = "head"            # قبعات، عصابات رأس
    TOP = "top"              # قمصان، بلايز، تيشيرتات
    OUTERWEAR = "outerwear"  # جواكيت، معاطف
    BOTTOM = "bottom"        # بناطيل، تنانير
    DRESS = "dress"          # فساتين (يغطي top+bottom)
    SHOES = "shoes"          # أحذية
    BAG = "bag"              # شنط
    ACCESSORY = "accessory"  # إكسسوارات (ساعات، نظارات، مجوهرات)


class PaymentMethodType(str, PyEnum):
    """أنواع وسائل الدفع"""
    CARD = "card"                    # بطاقة ائتمان/خصم
    PAYPAL = "paypal"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"
    WALLET = "wallet"                # محفظة محلية (مدى، STC Pay)
    CASH_ON_DELIVERY = "cash_on_delivery"


class PaymentStatus(str, PyEnum):
    """حالة المعاملة المالية"""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"


# ============ ENUMS الاشتراكات والتاجر ============

class SubscriptionPlan(str, PyEnum):
    """نوع اشتراك التاجر"""
    FREE_TRIAL = "free_trial"   # فترة تجريبية مجانية (مدتها يحددها الأدمن)
    MONTHLY = "monthly"         # اشتراك شهري مدفوع - شهر كامل
    YEARLY = "yearly"           # اشتراك سنوي (للتوسّع مستقبلاً)


class SubscriptionStatus(str, PyEnum):
    """حالة الاشتراك"""
    ACTIVE = "active"           # ساري المفعول
    EXPIRED = "expired"         # انتهت مدته
    CANCELLED = "cancelled"     # ألغاه المستخدم (يبقى ساري حتى expires_at)


class NotificationType(str, PyEnum):
    """
    أنواع الإشعارات - يستخدمها الـ Flutter لاختيار الأيقونة/الشاشة.
    """
    NEW_MESSAGE = "new_message"            # رسالة جديدة في محادثة
    NEW_ORDER = "new_order"                # طلب جديد (يصل للبائع)
    ORDER_PLACED = "order_placed"          # تأكيد للمشتري أن طلبه سُجّل
    ORDER_STATUS = "order_status"          # تحديث حالة الطلب (تأكيد/شحن/تسليم)
    PRODUCT_LISTED = "product_listed"      # تم نشر منتج للبائع
    SUBSCRIPTION = "subscription"          # أحداث الاشتراك (بدأ/جُدّد/قارب الانتهاء)
    SYSTEM = "system"                      # إشعار عام من النظام


# ============ USER ============

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String, unique=True, nullable=True, index=True)
    hashed_password = Column(String, nullable=True)
    name = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    is_verified_seller = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    # ===== التاجر والصلاحيات =====
    # is_merchant: صار تاجراً مرة واحدة على الأقل (فعّل وضع البيع).
    #   ملاحظة: القدرة الفعلية على نشر المنتجات تعتمد على وجود اشتراك ساري،
    #   وليس على هذا الحقل وحده (انظر services/subscriptions.py).
    is_merchant = Column(Boolean, default=False, nullable=False)
    # is_admin: صلاحية إدارة إعدادات المنصة (تشغيل/إيقاف الفترة التجريبية...).
    is_admin = Column(Boolean, default=False, nullable=False)

    style_preferences = Column(JSON, nullable=True)

    rating = Column(Float, default=0.0)
    total_sales = Column(Integer, default=0)

    fcm_token = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    products = relationship("Product", back_populates="seller", cascade="all, delete-orphan")
    orders = relationship("Order", foreign_keys="Order.buyer_id", back_populates="buyer")
    reviews_received = relationship("Review", foreign_keys="Review.reviewee_id", back_populates="reviewee")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    # العلاقات الجديدة
    avatar = relationship("Avatar", back_populates="user", uselist=False, cascade="all, delete-orphan")
    payment_methods = relationship("PaymentMethod", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    outfits = relationship("Outfit", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship(
        "Subscription", back_populates="user",
        cascade="all, delete-orphan", order_by="Subscription.created_at.desc()"
    )


# ============ PRODUCT (موسّع) ============

class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=False)
    category = Column(String, nullable=False, index=True)
    # جديد: تصنيف فرعي (مثلاً Category=Accessories, Subcategory=Watches)
    subcategory = Column(String, nullable=True, index=True)
    # جديد: خانة القطعة على الأفاتار
    slot = Column(SAEnum(ProductSlot), nullable=True, index=True)

    size = Column(String, nullable=False)
    color = Column(String, nullable=False)
    brand = Column(String, nullable=False, index=True)
    condition = Column(SAEnum(Condition), nullable=False)

    sale_price = Column(Float, nullable=False, default=0.0)
    rental_price_per_day = Column(Float, nullable=True)
    listing_type = Column(SAEnum(ListingType), nullable=False)

    image_urls = Column(ARRAY(String), default=[])
    # جديد: صورة PNG شفافة لعرضها على الأفاتار (try-on)
    try_on_image_url = Column(String, nullable=True)

    # جديد: خصائص إضافية مرنة (material, style_tags, season...)
    # مثال: {"material": "Cotton", "style_tags": ["casual","summer"], "gender": "unisex"}
    attributes = Column(JSON, nullable=True, default=dict)

    seller_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    seller = relationship("User", back_populates="products")

    location = Column(String, nullable=True)
    is_available = Column(Boolean, default=True)

    view_count = Column(Integer, default=0)
    favorite_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    rentals = relationship("RentalBooking", back_populates="product", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="product")
    favorites = relationship("Favorite", back_populates="product", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_product_search", "category", "brand", "color"),
        Index("idx_product_slot", "slot", "subcategory"),
    )


# ============ AVATAR (جديد) ============

class Avatar(Base):
    """
    الأفاتار - الشخصية الافتراضية القابلة للتخصيص للمستخدم.
    يخزّن خصائص المظهر + القطع الملبوسة حالياً (try-on).
    """
    __tablename__ = "avatars"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)

    # خصائص المظهر
    skin_tone = Column(String, default="medium")    # light | medium | tan | dark | deep
    hair_style = Column(String, default="short")    # short | long | curly | bun | bald
    hair_color = Column(String, default="black")    # black | brown | blonde | red | grey
    body_type = Column(String, default="average")   # slim | average | athletic | curvy | plus
    gender_presentation = Column(String, default="neutral")  # male | female | neutral
    height_cm = Column(Integer, default=170)

    # القطع الملبوسة حالياً - dict { slot: product_id }
    # مثال: {"top": "uuid-1", "bottom": "uuid-2", "shoes": "uuid-3"}
    equipped_items = Column(JSON, nullable=True, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="avatar")


# ============ RENTAL ============

class RentalBooking(Base):
    __tablename__ = "rental_bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)

    rent_start = Column(Date, nullable=False)
    rent_end = Column(Date, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="rentals")
    order = relationship("Order", back_populates="rental_booking")

    __table_args__ = (
        Index("idx_rental_dates", "product_id", "rent_start", "rent_end"),
    )


# ============ ORDER ============

class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_number = Column(String, unique=True, nullable=False, index=True)

    buyer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    seller_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)

    order_type = Column(SAEnum(OrderType), nullable=False)
    status = Column(SAEnum(OrderStatus), default=OrderStatus.PENDING)

    subtotal = Column(Float, nullable=False)
    platform_fee = Column(Float, nullable=False)
    total = Column(Float, nullable=False)

    payment_intent_id = Column(String, nullable=True)
    paid_at = Column(DateTime, nullable=True)

    shipping_address = Column(JSON, nullable=True)
    tracking_number = Column(String, nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    buyer = relationship("User", foreign_keys=[buyer_id], back_populates="orders")
    seller = relationship("User", foreign_keys=[seller_id])
    product = relationship("Product")
    rental_booking = relationship("RentalBooking", back_populates="order", uselist=False)
    transaction = relationship("Transaction", back_populates="order", uselist=False)


# ============ PAYMENT METHOD (جديد) ============

class PaymentMethod(Base):
    """
    وسيلة دفع محفوظة للمستخدم.
    ملاحظة أمان: لا نخزّن رقم البطاقة كاملاً أبداً - فقط آخر 4 أرقام
    وأي معرّف من بوابة الدفع (Stripe payment_method_id مثلاً).
    """
    __tablename__ = "payment_methods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    type = Column(SAEnum(PaymentMethodType), nullable=False)
    label = Column(String, nullable=True)        # اسم تعريفي "بطاقتي الرئيسية"

    # حقول البطاقة (آمنة - بدون الرقم الكامل)
    card_brand = Column(String, nullable=True)   # visa | mastercard | mada
    card_last4 = Column(String, nullable=True)   # آخر 4 أرقام فقط
    card_exp_month = Column(Integer, nullable=True)
    card_exp_year = Column(Integer, nullable=True)

    # معرّف من بوابة الدفع الخارجية (لما نربط Stripe)
    provider_token = Column(String, nullable=True)

    is_default = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="payment_methods")


# ============ TRANSACTION (جديد) ============

class Transaction(Base):
    """
    سجل معاملة مالية - يربط الطلب بوسيلة الدفع والنتيجة.
    تصميم idempotent: كل معاملة لها idempotency_key فريد لمنع
    الدفع المزدوج لو انضغط الزر مرتين.
    """
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)

    amount = Column(Float, nullable=False)
    currency = Column(String, default="USD")

    method_type = Column(SAEnum(PaymentMethodType), nullable=False)
    status = Column(SAEnum(PaymentStatus), default=PaymentStatus.PENDING)

    # مفتاح فريد لمنع الدفع المزدوج (idempotency)
    idempotency_key = Column(String, unique=True, nullable=False, index=True)

    # معرّف المعاملة من بوابة الدفع الخارجية
    provider_transaction_id = Column(String, nullable=True)

    # رسالة الخطأ لو فشلت
    failure_reason = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="transactions")
    order = relationship("Order", back_populates="transaction")


# ============ OUTFIT (جديد) ============

class Outfit(Base):
    """
    طقم ملابس متناسق - مجموعة منتجات تُلبس مع بعض.
    يُنشأ إما يدوياً من المستخدم أو تلقائياً من الـ AI.
    """
    __tablename__ = "outfits"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    name = Column(String, nullable=False)        # "إطلالة كاجوال صيفية"
    occasion = Column(String, nullable=True)     # المناسبة
    description = Column(Text, nullable=True)    # شرح من الـ AI

    # قائمة معرّفات المنتجات بالطقم
    product_ids = Column(ARRAY(String), default=[])

    # السعر الكلي للطقم (محسوب وقت الإنشاء)
    total_price = Column(Float, default=0.0)

    # هل أنشأه الـ AI؟
    is_ai_generated = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="outfits")


# ============ SUBSCRIPTION (جديد) ============

class Subscription(Base):
    """
    اشتراك التاجر - يحدد قدرته على نشر المنتجات.

    منطق سليم:
    - free_trial: فترة تجريبية مجانية، is_trial=True، مدتها من إعدادات المنصة.
    - monthly: اشتراك مدفوع، شهر كامل (is_trial=False) بغضّ النظر عن أي تجربة سابقة.
    - القدرة على النشر = وجود اشتراك status=active و expires_at في المستقبل.
    - عند الدفع الشهري نمدّد من max(now, expires_at الحالي) حتى لا يخسر المستخدم
      وقتاً، ويضمن دائماً شهراً كاملاً على الأقل من الآن.
    """
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)

    plan = Column(SAEnum(SubscriptionPlan), nullable=False)
    status = Column(SAEnum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False)

    is_trial = Column(Boolean, default=False, nullable=False)
    auto_renew = Column(Boolean, default=False, nullable=False)

    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False, index=True)

    # المبلغ المدفوع لهذه الفترة (0 للتجربة المجانية)
    amount_paid = Column(Float, default=0.0)
    # ربط بمعاملة الدفع لو كان مدفوعاً
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="subscriptions")

    __table_args__ = (
        Index("idx_subscription_active", "user_id", "status", "expires_at"),
    )


# ============ PLATFORM SETTINGS (جديد) ============

class PlatformSetting(Base):
    """
    إعدادات المنصة القابلة للتحكم وقت التشغيل (بدون تعديل الكود).
    صف واحد فقط (singleton) - id ثابت = 1.

    أهمها:
    - free_trial_enabled: المفتاح الرئيسي لتشغيل/إيقاف الفترة التجريبية.
      عند التشغيل: أي مستخدم يقدر يصير تاجراً مجاناً.
      عند الإيقاف: تفعيل التاجر يتطلب اشتراكاً مدفوعاً (الاشتراكات التجريبية
      القائمة تبقى سارية حتى تنتهي - لا نقطع أحداً في منتصف تجربته).
    """
    __tablename__ = "platform_settings"

    id = Column(Integer, primary_key=True, default=1)

    free_trial_enabled = Column(Boolean, default=True, nullable=False)
    free_trial_days = Column(Integer, default=14, nullable=False)

    # سعر ومدة الاشتراك الشهري
    monthly_price = Column(Float, default=9.99, nullable=False)
    monthly_period_days = Column(Integer, default=30, nullable=False)
    currency = Column(String, default="USD", nullable=False)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============ CHAT ============

class ChatThread(Base):
    __tablename__ = "chat_threads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user1_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    user2_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # علاقات صريحة للطرفين (كانت مفقودة وتسبب AttributeError في chat.py)
    user1 = relationship("User", foreign_keys=[user1_id], viewonly=True)
    user2 = relationship("User", foreign_keys=[user2_id], viewonly=True)
    product = relationship("Product", foreign_keys=[product_id], viewonly=True)

    messages = relationship(
        "ChatMessage", back_populates="thread",
        cascade="all, delete-orphan", order_by="ChatMessage.created_at"
    )

    __table_args__ = (
        UniqueConstraint("user1_id", "user2_id", "product_id", name="unique_thread"),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id = Column(UUID(as_uuid=True), ForeignKey("chat_threads.id"), nullable=False)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    thread = relationship("ChatThread", back_populates="messages")


# ============ REVIEW ============

class Review(Base):
    __tablename__ = "reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    reviewee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=True)

    rating = Column(Float, nullable=False)
    comment = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    reviewee = relationship("User", foreign_keys=[reviewee_id], back_populates="reviews_received")
    product = relationship("Product", back_populates="reviews")


# ============ FAVORITES ============

class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="favorites")

    __table_args__ = (
        UniqueConstraint("user_id", "product_id", name="unique_favorite"),
    )


# ============ NOTIFICATIONS ============

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String, nullable=False)
    data = Column(JSON, nullable=True)
    is_read = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    user = relationship("User", back_populates="notifications")
