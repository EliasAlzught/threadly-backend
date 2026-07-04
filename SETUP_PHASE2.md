# Threadly Backend — النسخة الموسّعة (المرحلة 1 + 2)

هذا الفولدر هو الـ backend **كامل وجاهز** مع كل التوسعات مدموجة.

## ✅ شو فيه

دُمجت المرحلة 1 (Models + Schemas) والمرحلة 2 (APIs) فوق الـ backend الأصلي.

### الميزات الجديدة
- **توسعة الفئات** — subcategory + slot لكل منتج (أحذية، شنط، إكسسوارات، قبعات...)
- **الأفاتار** — شخصية قابلة للتخصيص + try-on (لبس القطع)
- **نظام الدفع** — وسائل دفع متعددة + checkout آمن (idempotent)
- **الأطقم** — بناء طقم متناسق بالـ AI

### الملفات المتغيّرة عن الأصل
```
app/
├── main.py                    ← محدّث (routers جديدة)
├── seed.py                    ← محدّث (15 منتج بفئات متنوعة)
├── models/__init__.py         ← محدّث (جداول: Avatar, PaymentMethod, Transaction, Outfit)
├── schemas/__init__.py        ← محدّث (schemas جديدة)
├── api/
│   ├── products.py            ← محدّث (فلترة slot/subcategory + /categories)
│   ├── avatars.py             ← جديد
│   ├── payments.py            ← جديد
│   └── outfits.py             ← جديد
└── services/
    └── outfit_builder.py      ← جديد
```

باقي الملفات (auth, chat, orders, stylist, uploads, config, security...) **زي ما هي** بدون تغيير.

---

## 📥 طريقة الاستخدام

### الخيار أ: استبدل الفولدر كامل
انسخ محتوى هذا الفولدر مكان `C:\Users\ASUS\Desktop\threadly-backend`.

⚠️ **انتبه**: ملف `.env` هنا نسخة قديمة. لو عدّلت الـ `.env` تبعك (مفتاح Groq جديد مثلاً)، احتفظ بنسختك.

### الخيار ب: انسخ الملفات المتغيّرة فقط
انسخ الـ 9 ملفات المذكورة فوق فقط، وخلّي الباقي زي ما هو.

---

## 🚀 التشغيل

```powershell
cd C:\Users\ASUS\Desktop\threadly-backend

# أعد البناء + قاعدة البيانات (أضفنا جداول جديدة)
docker compose down -v
docker compose up -d --build

# أضف البيانات التجريبية
docker compose exec api python -m app.seed
```

لازم تشوف:
```
✅ Seeded 3 users and 15 products
   Categories: Men, Women, Outerwear, Shoes, Accessories
   Slots: head, top, outerwear, bottom, dress, shoes, bag, accessory
```

### تأكد إنه شغّال
افتح http://localhost:8000/docs — لازم تشوف المجموعات الجديدة:
**Avatar · Payments · Outfits**

---

## 🆕 الـ Endpoints الجديدة

### `/api/avatars`
- `GET /avatars/me` — جلب الأفاتار (يُنشأ تلقائياً)
- `PUT /avatars/me` — تحديث المظهر
- `POST /avatars/me/equip` — لبس قطعة
- `DELETE /avatars/me/equip/{slot}` — خلع قطعة
- `GET /avatars/me/full` — الأفاتار + تفاصيل القطع

### `/api/payments`
- `GET /payments/methods` — وسائل الدفع المحفوظة
- `POST /payments/methods` — إضافة وسيلة
- `DELETE /payments/methods/{id}` — حذف
- `POST /payments/checkout` — دفع (منتج/طقم) — idempotent
- `GET /payments/transactions` — سجل المعاملات

### `/api/outfits`
- `POST /outfits/build` — بناء طقم بالـ AI
- `POST /outfits/save` — حفظ طقم
- `GET /outfits/me` — أطقمي
- `GET /outfits/{id}` — تفاصيل
- `DELETE /outfits/{id}` — حذف

### `/api/products` (محدّث)
- فلترة جديدة: `subcategory`, `slot`
- `GET /products/categories` — شجرة الفئات

---

## ⚠️ ملاحظات الدفع

- **الدفع وهمي حالياً** — `_process_payment()` في `payments.py` ينجح دائماً.
  نقطة ربط Stripe معلّمة بوضوح داخل الدالة لو حبيت تربطها لاحقاً.
- **idempotency** — لو انضغط زر الدفع مرتين بنفس `idempotency_key`، الدفعة الثانية
  ترجع نتيجة الأولى — لا دفع مزدوج.
- **Cash on Delivery** — حالته `pending` حتى التسليم.

---

## 🧪 اختبار سريع في Swagger

بعد تسجيل الدخول (`emma@test.com` / `password123`) + Authorize:

**بناء طقم** — `POST /api/outfits/build`:
```json
{
  "occasion": "Everyday",
  "style": "Casual",
  "favorite_colors": ["Blue", "White"],
  "required_slots": ["top", "bottom", "shoes"]
}
```

**تخصيص الأفاتار** — `PUT /api/avatars/me`:
```json
{ "skin_tone": "tan", "hair_style": "long", "body_type": "athletic" }
```

**الدفع** — `POST /api/payments/checkout`:
```json
{
  "product_ids": ["معرّف-منتج-من-قائمة-المنتجات"],
  "order_type": "purchase",
  "payment_method_type": "card",
  "idempotency_key": "test-12345678"
}
```

---

## 📋 الخطوة الجاية

بعد ما تتأكد إن كل الـ endpoints تشتغل، الخطوة الجاية هي **المرحلة 3** —
Flutter Models + Repositories + Blocs للميزات الأربعة.
