"""
Threadly Backend API
نقطة الدخول الرئيسية - النسخة الموسّعة

الإضافات:
- avatars       : الأفاتار والـ try-on
- payments      : وسائل الدفع والـ checkout
- outfits       : بناء وحفظ الأطقم
- merchant      : تفعيل التاجر والاشتراكات (تجربة مجانية + شهري)
- admin         : إدارة إعدادات المنصة (تشغيل/إيقاف التجربة المجانية)
- notifications : قائمة الإشعارات + تسجيل FCM
"""
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.session import engine, Base
from app.db.bootstrap import bootstrap_database
from app.services.realtime import manager
from app.api import (
    auth, products, stylist, orders, chat, uploads,
    avatars, payments, outfits,           # السابقة
    merchant, admin, notifications,       # الجديدة
)

logger = logging.getLogger("threadly")


# إنشاء جداول قاعدة البيانات
# في الإنتاج استخدم Alembic للـ migrations
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title=settings.APP_NAME,
    description="Threadly - منصة بيع وشراء وإيجار الملابس مع AI Stylist والأفاتار",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# تسجيل الـ routes
app.include_router(auth.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(stylist.router, prefix="/api")
app.include_router(orders.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(uploads.router, prefix="/api")
# الجديدة
app.include_router(avatars.router, prefix="/api")
app.include_router(payments.router, prefix="/api")
app.include_router(outfits.router, prefix="/api")
app.include_router(merchant.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")


@app.on_event("startup")
async def on_startup():
    """
    عند الإقلاع:
    1. نلتقط حلقة الأحداث الرئيسية ليتمكن مدير WebSocket من الدفع اللحظي
       من نقاط النهاية المتزامنة (sync).
    2. نهيّئ قاعدة البيانات (أعمدة جديدة + إعدادات المنصة + الأدمن).
    """
    try:
        manager.set_loop(asyncio.get_running_loop())
    except Exception as e:
        logger.warning("Could not capture event loop: %s", e)

    try:
        bootstrap_database()
    except Exception as e:
        logger.error("Database bootstrap failed: %s", e)


@app.get("/")
def root():
    return {
        "name": "Threadly API",
        "version": "2.0.0",
        "docs": "/docs",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}
