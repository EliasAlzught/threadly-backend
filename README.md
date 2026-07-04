# Threadly Backend 🧵

Backend مجاني بالكامل لتطبيق Threadly - بُني بـ FastAPI + PostgreSQL + AI.

## التقنيات المستخدمة

| التقنية | الاستخدام | التكلفة |
|---------|-----------|---------|
| FastAPI | Backend framework | مجاني |
| PostgreSQL | قاعدة البيانات | مجاني |
| Redis | كاش + خلفية | مجاني |
| MinIO | تخزين الصور (S3-compatible) | مجاني |
| Groq / Gemini / Ollama | AI Stylist | مجاني |
| Mailpit | اختبار الإيميل | مجاني |
| Docker Compose | تشغيل كل شي | مجاني |

**التكلفة الإجمالية للتطوير: $0**

## التشغيل بأمر واحد

### المتطلبات
- Docker Desktop ([حمله من هنا](https://www.docker.com/products/docker-desktop/))

### الخطوات

**1. احصل على مفتاح AI مجاني**

اذهب إلى **Groq** (الأسرع والأفضل المجاني):
- https://console.groq.com
- سجل حساب
- أنشئ API key (مجاني، بدون بطاقة ائتمانية)

أو **Gemini** من Google:
- https://aistudio.google.com/apikey
- مجاني تماماً

**2. أنشئ ملف `.env`**

```bash
cp .env.example .env
```

افتح `.env` وضع المفتاح:
```env
AI_PROVIDER=groq
GROQ_API_KEY=gsk_xxxxxxxxxxxxx
SECRET_KEY=any-random-long-string-for-jwt
```

**3. شغل كل شي**

```bash
docker compose up
```

هذا الأمر يشغل:
- ✅ PostgreSQL على المنفذ 5432
- ✅ Redis على المنفذ 6379
- ✅ MinIO على المنفذ 9000 (واجهة على 9001)
- ✅ Mailpit على المنفذ 8025
- ✅ FastAPI على المنفذ 8000

**4. افتح الـ API**

- 🔗 **API**: http://localhost:8000
- 📚 **Swagger Docs**: http://localhost:8000/docs (اختبر الـ APIs من هون)
- 📦 **MinIO Console**: http://localhost:9001 (admin / admin)
- 📧 **Mailpit**: http://localhost:8025

## نقاط الـ API الرئيسية

| Endpoint | الوصف |
|----------|--------|
| `POST /api/auth/signup` | تسجيل مستخدم جديد |
| `POST /api/auth/login` | تسجيل دخول |
| `GET /api/auth/me` | بيانات المستخدم الحالي |
| `GET /api/products` | قائمة المنتجات (مع فلاتر) |
| `POST /api/products` | إضافة منتج |
| `POST /api/products/{id}/favorite` | إضافة للمفضلة |
| `POST /api/orders` | إنشاء طلب (شراء/إيجار) |
| `GET /api/orders/me` | طلباتي |
| `POST /api/stylist/recommend` | توصيات الـ AI Stylist |
| `GET /api/chat/threads` | محادثاتي |
| `POST /api/chat/messages` | إرسال رسالة |
| `WS /api/chat/ws?token=` | WebSocket للـ real-time |
| `POST /api/uploads/image` | رفع صورة |

## ربط Flutter بالـ Backend

في تطبيق Flutter، عدل `services/auth_service.dart` و الباقي:

```dart
const String API_BASE = 'http://10.0.2.2:8000/api';  // Android emulator
// const String API_BASE = 'http://localhost:8000/api';  // iOS simulator
// const String API_BASE = 'http://YOUR_LOCAL_IP:8000/api';  // جهاز حقيقي
```

ثم استخدم `http` package:

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

final response = await http.post(
  Uri.parse('$API_BASE/auth/signup'),
  headers: {'Content-Type': 'application/json'},
  body: jsonEncode({
    'email': email,
    'password': password,
    'name': name,
  }),
);
```

## النشر للإنتاج (مجاني)

لما تكون جاهز للنشر، استخدم:

### الخيار 1: Railway (الأفضل، مجاني)
- https://railway.app
- $5 credit شهرياً مجاناً
- يدعم Docker Compose مباشرة
- PostgreSQL + Redis مدمجين

### الخيار 2: Render
- https://render.com
- Web service مجاني
- PostgreSQL مجاني (90 يوم، ثم $7)

### الخيار 3: Fly.io
- https://fly.io
- $5 credit شهرياً
- يدعم Docker

### للقاعدة فقط (لو ضايقتك):
- **Supabase**: قاعدة PostgreSQL مجانية + Auth
- **Neon**: PostgreSQL مجاني (serverless)
- **PlanetScale**: قاعدة بيانات مجانية

### للصور:
- **Cloudinary**: 25GB مجاناً
- **Backblaze B2**: 10GB مجاناً
- **Bunny.net**: $0.01/GB رخيص جداً

## الـ AI - أرخص الخيارات

### Groq (الأفضل) ⭐
- مجاني، سريع جداً (10x أسرع من OpenAI)
- 30 طلب/دقيقة
- نماذج: Llama 3.3 70B, Mixtral
- https://console.groq.com

### Gemini Flash
- 1500 طلب/يوم مجاناً
- جيد للـ multilingual
- https://aistudio.google.com

### Ollama (محلي 100%)
- يعمل على جهازك بدون انترنت
- يحتاج RAM 8GB+
- ```ollama pull llama3.2 && ollama serve```

## استكشاف الأخطاء

### "connection refused"
- تأكد من تشغيل Docker
- شغل `docker compose ps` للتحقق

### "AI not working"
- تحقق من المفتاح في `.env`
- زر `/api/stylist/health` للتأكد

### "image upload fails"
- تحقق من MinIO على http://localhost:9001
- المستخدم: minioadmin / minioadmin

## الخطوات التالية

- [ ] إضافة Stripe Webhooks للمدفوعات الحقيقية
- [ ] إضافة Email templates مع Jinja2
- [ ] إضافة pgvector للـ embeddings (AI أذكى)
- [ ] إضافة Celery للمهام الخلفية
- [ ] إضافة rate limiting
- [ ] إضافة Sentry لمراقبة الأخطاء
