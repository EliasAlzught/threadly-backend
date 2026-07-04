"""
Products endpoints - النسخة الموسّعة

التحديثات:
- دعم فلترة subcategory و slot
- _product_to_out يرجع الحقول الجديدة (subcategory, slot, try_on_image_url, attributes)
"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Product, User, Favorite, NotificationType
from app.schemas import ProductCreate, ProductUpdate, ProductOut
from app.api.deps import get_current_user, require_active_merchant
from app.services.notifications import notify

router = APIRouter(prefix="/products", tags=["Products"])


def _product_to_out(product: Product) -> dict:
    """تحويل Product لـ dict مع بيانات البائع + الحقول الجديدة"""
    return {
        "id": product.id,
        "title": product.title,
        "description": product.description,
        "category": product.category,
        "subcategory": product.subcategory,
        "slot": product.slot.value if product.slot else None,
        "size": product.size,
        "color": product.color,
        "brand": product.brand,
        "condition": product.condition.value,
        "sale_price": product.sale_price,
        "rental_price_per_day": product.rental_price_per_day,
        "listing_type": product.listing_type.value,
        "image_urls": product.image_urls or [],
        "try_on_image_url": product.try_on_image_url,
        "attributes": product.attributes or {},
        "location": product.location,
        "is_available": product.is_available,
        "view_count": product.view_count,
        "favorite_count": product.favorite_count,
        "seller_id": product.seller_id,
        "seller_name": product.seller.name if product.seller else "",
        "seller_rating": product.seller.rating if product.seller else 0.0,
        "created_at": product.created_at,
    }


@router.get("", response_model=list[ProductOut])
def list_products(
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    slot: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    size: Optional[str] = None,
    color: Optional[str] = None,
    condition: Optional[str] = None,
    listing_type: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """قائمة المنتجات مع فلاتر بحث موسّعة"""
    query = db.query(Product).filter(Product.is_available == True)

    if category and category != "All":
        query = query.filter(Product.category == category)
    if subcategory:
        query = query.filter(Product.subcategory == subcategory)
    if slot:
        query = query.filter(Product.slot == slot)
    if size:
        query = query.filter(Product.size == size)
    if color:
        query = query.filter(Product.color == color)
    if condition:
        query = query.filter(Product.condition == condition)
    if listing_type:
        query = query.filter(Product.listing_type == listing_type)
    if min_price is not None:
        query = query.filter(Product.sale_price >= min_price)
    if max_price is not None:
        query = query.filter(Product.sale_price <= max_price)
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Product.title.ilike(search_pattern),
                Product.brand.ilike(search_pattern),
                Product.description.ilike(search_pattern),
            )
        )

    query = query.order_by(Product.created_at.desc())
    products = query.offset((page - 1) * page_size).limit(page_size).all()

    return [_product_to_out(p) for p in products]


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    """
    قائمة الفئات والفئات الفرعية المتاحة.
    مفيد للـ Flutter لبناء قوائم الفلترة ديناميكياً.
    """
    rows = db.query(Product.category, Product.subcategory).distinct().all()
    tree: dict[str, set] = {}
    for cat, sub in rows:
        if not cat:
            continue
        tree.setdefault(cat, set())
        if sub:
            tree[cat].add(sub)
    return {cat: sorted(list(subs)) for cat, subs in tree.items()}


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: UUID, db: Session = Depends(get_db)):
    """تفاصيل منتج"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Product not found")

    product.view_count += 1
    db.commit()

    return _product_to_out(product)


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    data: ProductCreate,
    current_user: User = Depends(require_active_merchant),
    db: Session = Depends(get_db),
):
    """
    إنشاء منتج جديد.
    يتطلب اشتراك تاجر ساري (تجربة مجانية أو مدفوع) - تحرسه require_active_merchant.
    """
    product = Product(
        **data.model_dump(),
        seller_id=current_user.id,
    )
    db.add(product)
    db.commit()
    db.refresh(product)

    # إشعار تأكيد للبائع أن منتجه أصبح منشوراً
    notify(
        db, current_user.id,
        type=NotificationType.PRODUCT_LISTED,
        title="Your item is live ✅",
        message=f'"{product.title}" is now listed and visible to buyers.',
        data={"product_id": str(product.id)},
    )

    return _product_to_out(product)


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: UUID,
    data: ProductUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """تعديل منتج"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Product not found")
    if product.seller_id != current_user.id:
        raise HTTPException(403, "Not your product")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(product, field, value)

    db.commit()
    db.refresh(product)
    return _product_to_out(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """حذف منتج"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Product not found")
    if product.seller_id != current_user.id:
        raise HTTPException(403, "Not your product")

    db.delete(product)
    db.commit()


@router.post("/{product_id}/favorite", status_code=status.HTTP_200_OK)
def toggle_favorite(
    product_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """إضافة/إزالة من المفضلة"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(404, "Product not found")

    existing = db.query(Favorite).filter(
        and_(
            Favorite.user_id == current_user.id,
            Favorite.product_id == product_id,
        )
    ).first()

    if existing:
        db.delete(existing)
        product.favorite_count = max(0, product.favorite_count - 1)
        is_favorite = False
    else:
        fav = Favorite(user_id=current_user.id, product_id=product_id)
        db.add(fav)
        product.favorite_count += 1
        is_favorite = True

    db.commit()
    return {"is_favorite": is_favorite}


@router.get("/me/favorites", response_model=list[ProductOut])
def get_favorites(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """منتجات المستخدم المفضلة"""
    favorites = db.query(Favorite).filter(
        Favorite.user_id == current_user.id
    ).all()
    return [_product_to_out(f.product) for f in favorites if f.product]


@router.get("/me/listings", response_model=list[ProductOut])
def get_my_listings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """منتجات المستخدم الحالي"""
    products = db.query(Product).filter(
        Product.seller_id == current_user.id
    ).order_by(Product.created_at.desc()).all()
    return [_product_to_out(p) for p in products]
