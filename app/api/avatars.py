"""
Avatars endpoints - الأفاتار والـ try-on

الميزات:
- GET    /avatars/me              جلب أفاتار المستخدم (يُنشأ تلقائياً لو مش موجود)
- PUT    /avatars/me              تحديث مظهر الأفاتار
- POST   /avatars/me/equip        لبس قطعة على الأفاتار
- DELETE /avatars/me/equip/{slot} خلع قطعة
- GET    /avatars/me/full         الأفاتار + تفاصيل القطع الملبوسة
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Avatar, Product, User, ProductSlot
from app.schemas import AvatarUpdate, AvatarOut, EquipItemRequest, AvatarWithProducts
from app.api.deps import get_current_user
from app.api.products import _product_to_out

router = APIRouter(prefix="/avatars", tags=["Avatar"])


def _get_or_create_avatar(user: User, db: Session) -> Avatar:
    """يجلب أفاتار المستخدم أو ينشئ واحد افتراضي"""
    avatar = db.query(Avatar).filter(Avatar.user_id == user.id).first()
    if not avatar:
        avatar = Avatar(user_id=user.id, equipped_items={})
        db.add(avatar)
        db.commit()
        db.refresh(avatar)
    return avatar


def _avatar_to_out(avatar: Avatar) -> dict:
    return {
        "id": avatar.id,
        "user_id": avatar.user_id,
        "skin_tone": avatar.skin_tone,
        "hair_style": avatar.hair_style,
        "hair_color": avatar.hair_color,
        "body_type": avatar.body_type,
        "gender_presentation": avatar.gender_presentation,
        "height_cm": avatar.height_cm,
        "equipped_items": avatar.equipped_items or {},
        "created_at": avatar.created_at,
        "updated_at": avatar.updated_at,
    }


@router.get("/me", response_model=AvatarOut)
def get_my_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """جلب أفاتار المستخدم (يُنشأ افتراضي تلقائياً لو أول مرة)"""
    avatar = _get_or_create_avatar(current_user, db)
    return _avatar_to_out(avatar)


@router.put("/me", response_model=AvatarOut)
def update_my_avatar(
    data: AvatarUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """تحديث خصائص مظهر الأفاتار (لون بشرة، شعر، جسم...)"""
    avatar = _get_or_create_avatar(current_user, db)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(avatar, field, value)

    db.commit()
    db.refresh(avatar)
    return _avatar_to_out(avatar)


@router.post("/me/equip", response_model=AvatarOut)
def equip_item(
    data: EquipItemRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    لبس قطعة على الأفاتار.
    - يتحقق إن المنتج موجود
    - يحدد الـ slot (من الطلب أو من المنتج نفسه)
    - قاعدة: لبس فستان (dress) يخلع top + bottom، والعكس
    """
    avatar = _get_or_create_avatar(current_user, db)

    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(404, "Product not found")

    # تحديد الخانة: من الطلب أو من المنتج
    slot = data.slot or (product.slot.value if product.slot else None)
    if not slot:
        raise HTTPException(
            400,
            "Cannot determine slot for this product. Provide 'slot' explicitly.",
        )

    valid_slots = {s.value for s in ProductSlot}
    if slot not in valid_slots:
        raise HTTPException(400, f"Invalid slot. Must be one of: {valid_slots}")

    equipped = dict(avatar.equipped_items or {})

    # قاعدة التوافق: الفستان يغطي الجسم كامل
    if slot == "dress":
        equipped.pop("top", None)
        equipped.pop("bottom", None)
    elif slot in ("top", "bottom"):
        equipped.pop("dress", None)

    equipped[slot] = str(data.product_id)
    avatar.equipped_items = equipped

    # SQLAlchemy ما يكتشف تغيير الـ JSON تلقائياً - نعلّمه
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(avatar, "equipped_items")

    db.commit()
    db.refresh(avatar)
    return _avatar_to_out(avatar)


@router.delete("/me/equip/{slot}", response_model=AvatarOut)
def unequip_item(
    slot: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """خلع قطعة من خانة معيّنة"""
    avatar = _get_or_create_avatar(current_user, db)

    equipped = dict(avatar.equipped_items or {})
    if slot in equipped:
        equipped.pop(slot)
        avatar.equipped_items = equipped
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(avatar, "equipped_items")
        db.commit()
        db.refresh(avatar)

    return _avatar_to_out(avatar)


@router.get("/me/full", response_model=AvatarWithProducts)
def get_avatar_with_products(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    الأفاتار + تفاصيل المنتجات الملبوسة كاملة.
    يستخدمه الـ Flutter في شاشة الـ try-on لعرض الصور.
    """
    avatar = _get_or_create_avatar(current_user, db)
    equipped = avatar.equipped_items or {}

    equipped_products: dict = {}
    for slot, product_id in equipped.items():
        try:
            product = db.query(Product).filter(
                Product.id == UUID(product_id)
            ).first()
            equipped_products[slot] = _product_to_out(product) if product else None
        except (ValueError, TypeError):
            equipped_products[slot] = None

    return {
        "avatar": _avatar_to_out(avatar),
        "equipped_products": equipped_products,
    }
