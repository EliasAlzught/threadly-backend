"""
AI Stylist endpoints
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Product, User
from app.schemas import StylistRequest, StylistRecommendation, ProductOut
from app.services.ai_stylist import ai_stylist
from app.api.deps import get_current_user
from app.api.products import _product_to_out

router = APIRouter(prefix="/stylist", tags=["AI Stylist"])


@router.post("/recommend", response_model=StylistRecommendation)
async def get_recommendations(
    request: StylistRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    الحصول على توصيات الستايلست بناءً على تفضيلات المستخدم.

    يستخدم الـ AI (Groq/Gemini/Ollama) لتحليل المنتجات المتاحة
    واختيار أفضل توصيات وإطلالة كاملة.
    """
    # 1. جلب المنتجات المتاحة
    query = db.query(Product).filter(Product.is_available == True)

    if request.budget_min is not None:
        query = query.filter(Product.sale_price >= request.budget_min)
    if request.budget_max is not None:
        query = query.filter(Product.sale_price <= request.budget_max)

    # ركز على التصنيفات المفضلة
    if request.preferred_categories:
        query = query.filter(Product.category.in_(request.preferred_categories))

    products = query.limit(50).all()

    if not products:
        # fallback: جيب أي منتجات
        products = db.query(Product).filter(
            Product.is_available == True
        ).limit(50).all()

    # 2. حوّل المنتجات لـ dicts للـ AI
    products_data = [_product_to_out(p) for p in products]

    # 3. استدعي الـ AI
    preferences = {
        "style": request.style,
        "occasion": request.occasion,
        "body_type": request.body_type,
        "favorite_colors": request.favorite_colors,
        "preferred_categories": request.preferred_categories,
    }

    result = await ai_stylist.recommend_outfit(preferences, products_data)

    # 4. جهز الرد
    recommended_ids = result.get("recommended_product_ids", [])
    outfit_ids = result.get("outfit", {})
    explanation = result.get("explanation", "")

    # خرائط لتحويل IDs لـ ProductOut
    product_map = {str(p["id"]): p for p in products_data}

    recommended_products = [
        product_map[pid] for pid in recommended_ids if pid in product_map
    ]

    outfit = {
        slot: product_map.get(pid) if pid else None
        for slot, pid in outfit_ids.items()
    }

    # احفظ التفضيلات في الـ user profile
    current_user.style_preferences = preferences
    db.commit()

    return StylistRecommendation(
        products=recommended_products,
        outfit=outfit,
        explanation=explanation,
    )


@router.get("/health")
async def check_ai_status():
    """التحقق من حالة الـ AI provider"""
    return {
        "provider": ai_stylist.provider,
        "is_available": ai_stylist.client is not None,
        "model": getattr(ai_stylist, "model", None),
    }
