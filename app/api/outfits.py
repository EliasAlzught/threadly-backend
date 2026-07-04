"""
Outfits endpoints - بناء وحفظ الأطقم

الميزات:
- POST /outfits/build      بناء طقم متناسق بالـ AI (لا يحفظ)
- POST /outfits/save       حفظ طقم في حساب المستخدم
- GET  /outfits/me         أطقم المستخدم المحفوظة
- GET  /outfits/{id}       تفاصيل طقم
- DELETE /outfits/{id}     حذف طقم
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Outfit, Product, User
from app.schemas import (
    OutfitBuildRequest, OutfitOut, OutfitItem, OutfitSaveRequest,
)
from app.api.deps import get_current_user
from app.api.products import _product_to_out
from app.services.outfit_builder import outfit_builder

router = APIRouter(prefix="/outfits", tags=["Outfits"])


@router.post("/build", response_model=OutfitOut)
def build_outfit(
    data: OutfitBuildRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    يبني طقم ملابس متناسق بالـ AI (Groq).
    لا يحفظ الطقم - فقط يقترحه. للحفظ استخدم /outfits/save.
    """
    # نجلب المنتجات المتاحة اللي عندها slot (قابلة للتنسيق)
    query = db.query(Product).filter(
        Product.is_available == True,
        Product.slot.isnot(None),
    )

    # فلترة بالميزانية لو محددة
    if data.budget_max:
        query = query.filter(Product.sale_price <= data.budget_max)

    products = query.limit(200).all()

    if not products:
        raise HTTPException(404, "No products available to build an outfit")

    # نحضّر البيانات للخدمة
    products_data = [_product_to_out(p) for p in products]

    # نبني الطقم
    result = outfit_builder.build_outfit(
        request=data.model_dump(),
        available_products=products_data,
    )

    # نحوّل معرّفات المنتجات لكائنات كاملة
    items: list[dict] = []
    total_price = 0.0
    product_map = {str(p.id): p for p in products}

    for slot, product_id in result["items"].items():
        product = product_map.get(str(product_id))
        if product:
            items.append({
                "slot": slot,
                "product": _product_to_out(product),
            })
            total_price += product.sale_price

    if not items:
        raise HTTPException(404, "Could not build a valid outfit")

    return {
        "id": None,
        "name": result["name"],
        "occasion": data.occasion,
        "description": result["description"],
        "items": items,
        "total_price": round(total_price, 2),
        "is_ai_generated": True,
        "created_at": None,
    }


@router.post("/save", response_model=OutfitOut, status_code=201)
def save_outfit(
    data: OutfitSaveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """حفظ طقم في حساب المستخدم"""
    # نتحقق إن المنتجات موجودة
    products = db.query(Product).filter(
        Product.id.in_(data.product_ids)
    ).all()

    if len(products) != len(data.product_ids):
        raise HTTPException(404, "One or more products not found")

    total_price = sum(p.sale_price for p in products)

    outfit = Outfit(
        user_id=current_user.id,
        name=data.name,
        occasion=data.occasion,
        description=data.description,
        product_ids=[str(pid) for pid in data.product_ids],
        total_price=round(total_price, 2),
        is_ai_generated=False,
    )
    db.add(outfit)
    db.commit()
    db.refresh(outfit)

    return _outfit_to_out(outfit, db)


@router.get("/me", response_model=list[OutfitOut])
def my_outfits(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """أطقم المستخدم المحفوظة"""
    outfits = db.query(Outfit).filter(
        Outfit.user_id == current_user.id
    ).order_by(Outfit.created_at.desc()).all()
    return [_outfit_to_out(o, db) for o in outfits]


@router.get("/{outfit_id}", response_model=OutfitOut)
def get_outfit(
    outfit_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """تفاصيل طقم"""
    outfit = db.query(Outfit).filter(
        Outfit.id == outfit_id,
        Outfit.user_id == current_user.id,
    ).first()
    if not outfit:
        raise HTTPException(404, "Outfit not found")
    return _outfit_to_out(outfit, db)


@router.delete("/{outfit_id}", status_code=204)
def delete_outfit(
    outfit_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """حذف طقم"""
    outfit = db.query(Outfit).filter(
        Outfit.id == outfit_id,
        Outfit.user_id == current_user.id,
    ).first()
    if not outfit:
        raise HTTPException(404, "Outfit not found")
    db.delete(outfit)
    db.commit()


# ============ Helper ============

def _outfit_to_out(outfit: Outfit, db: Session) -> dict:
    """تحويل Outfit لـ dict مع تفاصيل المنتجات"""
    items: list[dict] = []
    for pid in (outfit.product_ids or []):
        try:
            product = db.query(Product).filter(Product.id == UUID(pid)).first()
            if product:
                items.append({
                    "slot": product.slot.value if product.slot else "item",
                    "product": _product_to_out(product),
                })
        except (ValueError, TypeError):
            continue

    return {
        "id": outfit.id,
        "name": outfit.name,
        "occasion": outfit.occasion,
        "description": outfit.description,
        "items": items,
        "total_price": outfit.total_price,
        "is_ai_generated": outfit.is_ai_generated,
        "created_at": outfit.created_at,
    }
