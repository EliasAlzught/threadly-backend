"""
Pydantic schemas - النسخة الموسّعة

التوسعات:
- ProductCreate/Out: + subcategory, slot, try_on_image_url, attributes
- Avatar schemas: تخصيص + try-on
- Payment schemas: وسائل دفع + معاملات
- Outfit schemas: بناء أطقم + حفظها
"""
from datetime import datetime, date
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


# ============ AUTH ============

class UserSignUp(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=2)
    phone: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


# ============ USER ============

class StylePreferences(BaseModel):
    style: Optional[str] = None
    occasion: Optional[str] = None
    body_type: Optional[str] = None
    favorite_colors: list[str] = []
    preferred_categories: list[str] = []


class UserOut(BaseModel):
    id: UUID
    email: str
    name: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_verified_seller: bool = False
    is_merchant: bool = False
    is_admin: bool = False
    rating: float = 0.0
    total_sales: int = 0
    style_preferences: Optional[StylePreferences] = None
    created_at: datetime

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    style_preferences: Optional[StylePreferences] = None


# ============ PRODUCT (موسّع) ============

class ProductCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str
    category: str
    subcategory: Optional[str] = None          # جديد
    slot: Optional[str] = None                 # جديد: head|top|outerwear|bottom|dress|shoes|bag|accessory
    size: str
    color: str
    brand: str
    condition: str
    sale_price: float = Field(ge=0)
    rental_price_per_day: Optional[float] = Field(default=None, ge=0)
    listing_type: str
    image_urls: list[str] = []
    try_on_image_url: Optional[str] = None     # جديد
    attributes: Optional[dict] = None          # جديد
    location: Optional[str] = None


class ProductUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    subcategory: Optional[str] = None
    slot: Optional[str] = None
    sale_price: Optional[float] = None
    rental_price_per_day: Optional[float] = None
    image_urls: Optional[list[str]] = None
    try_on_image_url: Optional[str] = None
    attributes: Optional[dict] = None
    is_available: Optional[bool] = None


class ProductOut(BaseModel):
    id: UUID
    title: str
    description: str
    category: str
    subcategory: Optional[str] = None          # جديد
    slot: Optional[str] = None                 # جديد
    size: str
    color: str
    brand: str
    condition: str
    sale_price: float
    rental_price_per_day: Optional[float]
    listing_type: str
    image_urls: list[str]
    try_on_image_url: Optional[str] = None      # جديد
    attributes: Optional[dict] = None           # جديد
    location: Optional[str]
    is_available: bool
    view_count: int
    favorite_count: int
    seller_id: UUID
    seller_name: str
    seller_rating: float
    created_at: datetime

    class Config:
        from_attributes = True


class ProductFilter(BaseModel):
    category: Optional[str] = None
    subcategory: Optional[str] = None          # جديد
    slot: Optional[str] = None                 # جديد
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    size: Optional[str] = None
    color: Optional[str] = None
    condition: Optional[str] = None
    listing_type: Optional[str] = None
    search: Optional[str] = None
    page: int = 1
    page_size: int = 20


# ============ AVATAR (جديد) ============

class AvatarUpdate(BaseModel):
    """تحديث خصائص مظهر الأفاتار"""
    skin_tone: Optional[str] = None       # light|medium|tan|dark|deep
    hair_style: Optional[str] = None      # short|long|curly|bun|bald
    hair_color: Optional[str] = None      # black|brown|blonde|red|grey
    body_type: Optional[str] = None       # slim|average|athletic|curvy|plus
    gender_presentation: Optional[str] = None  # male|female|neutral
    height_cm: Optional[int] = Field(default=None, ge=120, le=220)


class EquipItemRequest(BaseModel):
    """طلب لبس قطعة على الأفاتار"""
    product_id: UUID
    slot: str   # الخانة المراد لبسها فيها


class AvatarOut(BaseModel):
    id: UUID
    user_id: UUID
    skin_tone: str
    hair_style: str
    hair_color: str
    body_type: str
    gender_presentation: str
    height_cm: int
    equipped_items: dict          # { slot: product_id }
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AvatarWithProducts(BaseModel):
    """الأفاتار + تفاصيل المنتجات الملبوسة (للعرض في try-on)"""
    avatar: AvatarOut
    equipped_products: dict[str, Optional[ProductOut]]  # { slot: ProductOut }


# ============ PAYMENT METHOD (جديد) ============

class PaymentMethodCreate(BaseModel):
    """
    إضافة وسيلة دفع.
    ملاحظة: للبطاقة، الـ Flutter يرسل فقط آخر 4 أرقام + الماركة.
    الرقم الكامل لا يمر عبر السيرفر إطلاقاً (يُعالج ببوابة الدفع).
    """
    type: str  # card|paypal|apple_pay|google_pay|wallet|cash_on_delivery
    label: Optional[str] = None
    card_brand: Optional[str] = None
    card_last4: Optional[str] = Field(default=None, max_length=4)
    card_exp_month: Optional[int] = Field(default=None, ge=1, le=12)
    card_exp_year: Optional[int] = None
    provider_token: Optional[str] = None
    is_default: bool = False


class PaymentMethodOut(BaseModel):
    id: UUID
    type: str
    label: Optional[str]
    card_brand: Optional[str]
    card_last4: Optional[str]
    card_exp_month: Optional[int]
    card_exp_year: Optional[int]
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============ ORDER + PAYMENT (موسّع) ============

class OrderCreate(BaseModel):
    product_id: UUID
    order_type: str
    rent_start: Optional[date] = None
    rent_end: Optional[date] = None
    shipping_address: Optional[dict] = None
    # جديد: وسيلة الدفع
    payment_method_id: Optional[UUID] = None
    payment_method_type: Optional[str] = None  # لو دفع لأول مرة بدون حفظ


class CheckoutRequest(BaseModel):
    """
    طلب دفع موحّد - يدعم منتج واحد أو طقم كامل.
    idempotency_key يمنع الدفع المزدوج.
    """
    product_ids: list[UUID]                      # منتج أو أكثر (طقم)
    order_type: str = "purchase"                 # purchase | rental
    payment_method_type: str                     # card|wallet|cash_on_delivery...
    payment_method_id: Optional[UUID] = None     # وسيلة محفوظة (اختياري)
    rent_start: Optional[date] = None
    rent_end: Optional[date] = None
    shipping_address: Optional[dict] = None
    idempotency_key: str = Field(min_length=8)   # مفتاح فريد من العميل


class TransactionOut(BaseModel):
    id: UUID
    amount: float
    currency: str
    method_type: str
    status: str
    order_id: Optional[UUID]
    provider_transaction_id: Optional[str]
    failure_reason: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class CheckoutResponse(BaseModel):
    """نتيجة الدفع"""
    success: bool
    transaction: TransactionOut
    orders: list["OrderOut"]
    message: str


class OrderOut(BaseModel):
    id: UUID
    order_number: str
    order_type: str
    status: str
    subtotal: float
    platform_fee: float
    total: float
    product_id: UUID
    buyer_id: UUID
    seller_id: UUID
    tracking_number: Optional[str]
    paid_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============ OUTFIT (جديد) ============

class OutfitBuildRequest(BaseModel):
    """
    طلب بناء طقم كامل من الـ AI.
    الـ AI يختار قطع متناسقة (top+bottom+shoes+accessory) حسب التفضيلات.
    """
    occasion: str                                 # العمل، حفلة، يومي...
    style: Optional[str] = None
    favorite_colors: list[str] = []
    budget_max: Optional[float] = None
    # خانات مطلوبة بالطقم (لو فاضي = الافتراضي)
    required_slots: list[str] = []                # ["top","bottom","shoes"]
    gender: Optional[str] = None


class OutfitItem(BaseModel):
    """قطعة واحدة بالطقم مع سبب اختيارها"""
    slot: str
    product: ProductOut


class OutfitOut(BaseModel):
    id: Optional[UUID] = None
    name: str
    occasion: Optional[str]
    description: Optional[str]
    items: list[OutfitItem]
    total_price: float
    is_ai_generated: bool
    created_at: Optional[datetime] = None


class OutfitSaveRequest(BaseModel):
    """حفظ طقم في حساب المستخدم"""
    name: str = Field(min_length=2, max_length=120)
    occasion: Optional[str] = None
    description: Optional[str] = None
    product_ids: list[UUID]


# ============ CHAT ============

class MessageCreate(BaseModel):
    thread_id: Optional[UUID] = None
    recipient_id: Optional[UUID] = None
    product_id: Optional[UUID] = None
    content: str = Field(min_length=1, max_length=2000)


class MessageOut(BaseModel):
    id: UUID
    thread_id: UUID
    sender_id: UUID
    content: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============ AI STYLIST ============

class StylistRequest(BaseModel):
    style: str
    occasion: str
    body_type: str
    favorite_colors: list[str]
    preferred_categories: list[str]
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None


class StylistRecommendation(BaseModel):
    products: list[ProductOut]
    outfit: dict[str, Optional[ProductOut]]
    explanation: str


# ============ REVIEW ============

class ReviewCreate(BaseModel):
    reviewee_id: UUID
    product_id: Optional[UUID] = None
    order_id: Optional[UUID] = None
    rating: float = Field(ge=1, le=5)
    comment: Optional[str] = None


class ReviewOut(BaseModel):
    id: UUID
    reviewer_id: UUID
    reviewer_name: str
    rating: float
    comment: Optional[str]
    product_title: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ============ SUBSCRIPTION / MERCHANT (جديد) ============

class SubscriptionInfo(BaseModel):
    id: UUID
    plan: str
    status: str
    is_trial: bool
    auto_renew: bool
    started_at: datetime
    expires_at: datetime
    days_left: int


class SubscriptionStatusOut(BaseModel):
    """ملخّص حالة التاجر/الاشتراك للـ Flutter."""
    is_merchant: bool
    can_list_products: bool
    has_active_subscription: bool
    free_trial_enabled: bool
    can_start_free_trial: bool
    free_trial_days: int
    monthly_price: float
    monthly_period_days: int
    currency: str
    subscription: Optional[SubscriptionInfo] = None


class SubscribeRequest(BaseModel):
    """
    طلب اشتراك شهري مدفوع.
    idempotency_key يمنع الخصم المزدوج لو انضغط الزر مرتين.
    """
    payment_method_type: str = "card"          # card|wallet|paypal...
    payment_method_id: Optional[UUID] = None   # وسيلة محفوظة (اختياري)
    auto_renew: bool = False
    idempotency_key: str = Field(min_length=8)


# ============ ADMIN / PLATFORM SETTINGS (جديد) ============

class PlatformSettingsOut(BaseModel):
    free_trial_enabled: bool
    free_trial_days: int
    monthly_price: float
    monthly_period_days: int
    currency: str
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PlatformSettingsUpdate(BaseModel):
    """تحديث جزئي - أي حقل None يبقى كما هو."""
    free_trial_enabled: Optional[bool] = None
    free_trial_days: Optional[int] = Field(default=None, ge=1, le=365)
    monthly_price: Optional[float] = Field(default=None, ge=0)
    monthly_period_days: Optional[int] = Field(default=None, ge=1, le=366)
    currency: Optional[str] = None


# ============ NOTIFICATIONS (جديد) ============

class NotificationOut(BaseModel):
    id: UUID
    title: str
    message: str
    type: str
    data: Optional[dict] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationListOut(BaseModel):
    items: list[NotificationOut]
    unread_count: int


class FcmTokenRequest(BaseModel):
    """تسجيل/تحديث رمز جهاز FCM لاستقبال Push."""
    fcm_token: str = Field(min_length=10)


# تحديث forward references
Token.model_rebuild()
CheckoutResponse.model_rebuild()
