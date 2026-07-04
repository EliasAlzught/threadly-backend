"""
سكربت البيانات التجريبية - النسخة الموسّعة

شغله بعد تشغيل الـ API:
    docker compose exec api python -m app.seed

الجديد:
- منتجات بفئات متنوعة (أحذية، شنط، إكسسوارات، قبعات)
- كل منتج له slot (لدعم الأفاتار وبناء الأطقم)
- subcategory و attributes
- try_on_image_url
"""
import uuid
from sqlalchemy.orm import Session
from app.db.session import SessionLocal, engine, Base
from app.models import User, Product, Avatar, Condition, ListingType, ProductSlot
from app.core.security import hash_password


def seed_data():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        if db.query(User).count() > 0:
            print("Data already exists. Skipping.")
            return

        # ===== مستخدمين تجريبيين =====
        sellers = [
            User(
                id=uuid.uuid4(),
                email="emma@test.com",
                name="Emma Stone",
                hashed_password=hash_password("password123"),
                is_verified_seller=True,
                rating=4.8,
                total_sales=24,
            ),
            User(
                id=uuid.uuid4(),
                email="sofia@test.com",
                name="Sofia Martinez",
                hashed_password=hash_password("password123"),
                is_verified_seller=True,
                rating=4.9,
                total_sales=42,
            ),
            User(
                id=uuid.uuid4(),
                email="james@test.com",
                name="James Wilson",
                hashed_password=hash_password("password123"),
                rating=4.7,
                total_sales=15,
            ),
        ]
        db.add_all(sellers)
        db.flush()

        # أفاتار افتراضي لكل مستخدم
        for s in sellers:
            db.add(Avatar(user_id=s.id, equipped_items={}))

        # ===== منتجات متنوعة بكل الفئات والخانات =====
        IMG = "https://images.unsplash.com/"
        products = [
            # ---- TOP (قمصان وبلايز) ----
            Product(
                title="White Cotton T-Shirt", description="Essential white tee, soft cotton.",
                category="Men", subcategory="T-Shirts", slot=ProductSlot.TOP,
                size="M", color="White", brand="Uniqlo", condition=Condition.BRAND_NEW,
                sale_price=20.0, rental_price_per_day=3.0, listing_type=ListingType.BOTH,
                image_urls=[f"{IMG}photo-1521572163474-6864f9cf17ab?w=600"],
                try_on_image_url=f"{IMG}photo-1521572163474-6864f9cf17ab?w=400",
                attributes={"material": "Cotton", "style_tags": ["casual", "basic"], "season": "all"},
                seller_id=sellers[0].id, location="Amsterdam",
            ),
            Product(
                title="Silk Blouse", description="Elegant silk blouse for formal occasions.",
                category="Women", subcategory="Blouses", slot=ProductSlot.TOP,
                size="S", color="Beige", brand="Zara", condition=Condition.LIKE_NEW,
                sale_price=48.0, rental_price_per_day=7.0, listing_type=ListingType.BOTH,
                image_urls=[f"{IMG}photo-1564257631407-4deb1f99d992?w=600"],
                try_on_image_url=f"{IMG}photo-1564257631407-4deb1f99d992?w=400",
                attributes={"material": "Silk", "style_tags": ["formal", "elegant"], "season": "all"},
                seller_id=sellers[1].id, location="Rotterdam",
            ),
            # ---- BOTTOM (بناطيل وتنانير) ----
            Product(
                title="Slim Fit Jeans", description="Dark wash slim fit denim jeans.",
                category="Men", subcategory="Jeans", slot=ProductSlot.BOTTOM,
                size="M", color="Blue", brand="Levi's", condition=Condition.LIKE_NEW,
                sale_price=55.0, rental_price_per_day=6.0, listing_type=ListingType.BOTH,
                image_urls=[f"{IMG}photo-1542272604-787c3835535d?w=600"],
                try_on_image_url=f"{IMG}photo-1542272604-787c3835535d?w=400",
                attributes={"material": "Denim", "style_tags": ["casual"], "season": "all"},
                seller_id=sellers[2].id, location="The Hague",
            ),
            Product(
                title="Pleated Midi Skirt", description="Flowy pleated midi skirt, versatile.",
                category="Women", subcategory="Skirts", slot=ProductSlot.BOTTOM,
                size="S", color="Black", brand="Mango", condition=Condition.BRAND_NEW,
                sale_price=38.0, rental_price_per_day=5.0, listing_type=ListingType.BOTH,
                image_urls=[f"{IMG}photo-1583496661160-fb5886a0aaaa?w=600"],
                try_on_image_url=f"{IMG}photo-1583496661160-fb5886a0aaaa?w=400",
                attributes={"material": "Polyester", "style_tags": ["formal", "elegant"], "season": "all"},
                seller_id=sellers[1].id, location="Utrecht",
            ),
            # ---- DRESS (فساتين) ----
            Product(
                title="Floral Summer Dress", description="Beautiful floral pattern, lightweight.",
                category="Women", subcategory="Casual Dresses", slot=ProductSlot.DRESS,
                size="S", color="Pink", brand="Zara", condition=Condition.BRAND_NEW,
                sale_price=45.0, rental_price_per_day=6.0, listing_type=ListingType.BOTH,
                image_urls=[f"{IMG}photo-1572804013309-59a88b7e92f1?w=600"],
                try_on_image_url=f"{IMG}photo-1572804013309-59a88b7e92f1?w=400",
                attributes={"material": "Cotton", "style_tags": ["casual", "summer"], "season": "summer"},
                seller_id=sellers[1].id, location="Rotterdam",
            ),
            # ---- OUTERWEAR (جواكيت ومعاطف) ----
            Product(
                title="Vintage Denim Jacket", description="Classic vintage denim jacket.",
                category="Outerwear", subcategory="Jackets", slot=ProductSlot.OUTERWEAR,
                size="M", color="Blue", brand="Levi's", condition=Condition.LIKE_NEW,
                sale_price=65.0, rental_price_per_day=8.0, listing_type=ListingType.BOTH,
                image_urls=[f"{IMG}photo-1544022613-e87ca75a784a?w=600"],
                try_on_image_url=f"{IMG}photo-1544022613-e87ca75a784a?w=400",
                attributes={"material": "Denim", "style_tags": ["casual", "vintage"], "season": "spring"},
                seller_id=sellers[0].id, location="Amsterdam",
            ),
            Product(
                title="Wool Winter Coat", description="Cozy wool blend coat in classic grey.",
                category="Outerwear", subcategory="Coats", slot=ProductSlot.OUTERWEAR,
                size="M", color="Grey", brand="Mango", condition=Condition.LIKE_NEW,
                sale_price=95.0, rental_price_per_day=12.0, listing_type=ListingType.BOTH,
                image_urls=[f"{IMG}photo-1539109136881-3be0616acf4b?w=600"],
                try_on_image_url=f"{IMG}photo-1539109136881-3be0616acf4b?w=400",
                attributes={"material": "Wool", "style_tags": ["formal", "warm"], "season": "winter"},
                seller_id=sellers[1].id, location="Utrecht",
            ),
            # ---- SHOES (أحذية) ----
            Product(
                title="White Leather Sneakers", description="Clean white leather sneakers.",
                category="Shoes", subcategory="Sneakers", slot=ProductSlot.SHOES,
                size="42", color="White", brand="Nike", condition=Condition.LIKE_NEW,
                sale_price=75.0, listing_type=ListingType.SALE,
                image_urls=[f"{IMG}photo-1542291026-7eec264c27ff?w=600"],
                try_on_image_url=f"{IMG}photo-1542291026-7eec264c27ff?w=400",
                attributes={"material": "Leather", "style_tags": ["casual", "sporty"], "season": "all"},
                seller_id=sellers[0].id, location="Amsterdam",
            ),
            Product(
                title="Black Leather Heels", description="Elegant black heels for formal events.",
                category="Shoes", subcategory="Heels", slot=ProductSlot.SHOES,
                size="38", color="Black", brand="Aldo", condition=Condition.LIKE_NEW,
                sale_price=60.0, rental_price_per_day=8.0, listing_type=ListingType.BOTH,
                image_urls=[f"{IMG}photo-1543163521-1bf539c55dd2?w=600"],
                try_on_image_url=f"{IMG}photo-1543163521-1bf539c55dd2?w=400",
                attributes={"material": "Leather", "style_tags": ["formal", "elegant"], "season": "all"},
                seller_id=sellers[1].id, location="Rotterdam",
            ),
            # ---- BAG (شنط) ----
            Product(
                title="Leather Tote Bag", description="Spacious brown leather tote bag.",
                category="Accessories", subcategory="Bags", slot=ProductSlot.BAG,
                size="One Size", color="Brown", brand="Fossil", condition=Condition.LIKE_NEW,
                sale_price=85.0, rental_price_per_day=10.0, listing_type=ListingType.BOTH,
                image_urls=[f"{IMG}photo-1584917865442-de89df76afd3?w=600"],
                try_on_image_url=f"{IMG}photo-1584917865442-de89df76afd3?w=400",
                attributes={"material": "Leather", "style_tags": ["casual", "practical"], "season": "all"},
                seller_id=sellers[2].id, location="The Hague",
            ),
            Product(
                title="Mini Crossbody Bag", description="Compact crossbody bag, perfect for nights out.",
                category="Accessories", subcategory="Bags", slot=ProductSlot.BAG,
                size="One Size", color="Black", brand="Charles & Keith", condition=Condition.BRAND_NEW,
                sale_price=42.0, listing_type=ListingType.SALE,
                image_urls=[f"{IMG}photo-1548036328-c9fa89d128fa?w=600"],
                try_on_image_url=f"{IMG}photo-1548036328-c9fa89d128fa?w=400",
                attributes={"material": "Synthetic", "style_tags": ["party", "elegant"], "season": "all"},
                seller_id=sellers[1].id, location="Rotterdam",
            ),
            # ---- ACCESSORY (إكسسوارات) ----
            Product(
                title="Classic Wristwatch", description="Minimalist analog watch with leather strap.",
                category="Accessories", subcategory="Watches", slot=ProductSlot.ACCESSORY,
                size="One Size", color="Brown", brand="Daniel Wellington", condition=Condition.LIKE_NEW,
                sale_price=120.0, listing_type=ListingType.SALE,
                image_urls=[f"{IMG}photo-1524592094714-0f0654e20314?w=600"],
                try_on_image_url=f"{IMG}photo-1524592094714-0f0654e20314?w=400",
                attributes={"material": "Steel", "style_tags": ["formal", "classic"], "season": "all"},
                seller_id=sellers[2].id, location="The Hague",
            ),
            Product(
                title="Gold Hoop Earrings", description="Elegant gold-plated hoop earrings.",
                category="Accessories", subcategory="Jewelry", slot=ProductSlot.ACCESSORY,
                size="One Size", color="Yellow", brand="Pandora", condition=Condition.BRAND_NEW,
                sale_price=55.0, listing_type=ListingType.SALE,
                image_urls=[f"{IMG}photo-1535632066927-ab7c9ab60908?w=600"],
                try_on_image_url=f"{IMG}photo-1535632066927-ab7c9ab60908?w=400",
                attributes={"material": "Gold-plated", "style_tags": ["elegant", "party"], "season": "all"},
                seller_id=sellers[0].id, location="Amsterdam",
            ),
            # ---- HEAD (قبعات) ----
            Product(
                title="Wool Beanie", description="Warm knitted wool beanie.",
                category="Accessories", subcategory="Hats", slot=ProductSlot.HEAD,
                size="One Size", color="Grey", brand="H&M", condition=Condition.BRAND_NEW,
                sale_price=18.0, listing_type=ListingType.SALE,
                image_urls=[f"{IMG}photo-1576871337622-98d48d1cf531?w=600"],
                try_on_image_url=f"{IMG}photo-1576871337622-98d48d1cf531?w=400",
                attributes={"material": "Wool", "style_tags": ["casual", "warm"], "season": "winter"},
                seller_id=sellers[1].id, location="Utrecht",
            ),
            # ---- منتج رسمي إضافي ----
            Product(
                title="Elegant Black Tuxedo", description="Sharp tuxedo, worn once. Dry cleaned.",
                category="Men", subcategory="Suits", slot=ProductSlot.TOP,
                size="L", color="Black", brand="Hugo Boss", condition=Condition.LIKE_NEW,
                sale_price=350.0, rental_price_per_day=35.0, listing_type=ListingType.RENTAL,
                image_urls=[f"{IMG}photo-1593030761757-71fae45fa0e7?w=600"],
                try_on_image_url=f"{IMG}photo-1593030761757-71fae45fa0e7?w=400",
                attributes={"material": "Wool", "style_tags": ["formal", "luxury"], "season": "all"},
                seller_id=sellers[2].id, location="The Hague",
            ),
        ]
        db.add_all(products)
        db.commit()

        print(f"✅ Seeded {len(sellers)} users and {len(products)} products")
        print(f"   Categories: Men, Women, Outerwear, Shoes, Accessories")
        print(f"   Slots: head, top, outerwear, bottom, dress, shoes, bag, accessory")
        print("\nاختبر تسجيل الدخول:")
        print("  Email: emma@test.com")
        print("  Password: password123")

    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
