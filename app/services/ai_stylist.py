"""
خدمة الذكاء الاصطناعي للـ Stylist

يدعم 3 مزودين مجانيين:
1. Groq - سريع جداً، مجاني، يستخدم Llama 3.3 و Mixtral
   - احصل على API key من: https://console.groq.com
   - الحد المجاني: ~30 طلب/دقيقة، سخي جداً

2. Gemini - من Google، مجاني
   - احصل على API key من: https://aistudio.google.com/apikey
   - الحد المجاني: 1500 طلب/يوم لـ Gemini Flash

3. Ollama - يعمل محلياً على جهازك، مجاني تماماً
   - حمل من: https://ollama.com
   - تشغيل: ollama pull llama3.2 ثم ollama serve
"""
import json
import logging
from typing import Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """أنت مساعد أزياء ذكي لتطبيق Threadly.
مهمتك مساعدة المستخدمين في اختيار الملابس المناسبة بناءً على:
- نمط الموضة المفضل (style)
- المناسبة (occasion)
- نوع الجسم (body type)
- الألوان المفضلة
- التصنيفات المهتمين بها

يجب أن تقوم بـ:
1. تحليل المنتجات المتاحة
2. اختيار أفضل 10 منتجات تناسب المستخدم
3. اقتراح إطلالة كاملة (Top, Outerwear, Shoes, Accessory)
4. شرح مختصر ليش هذه المنتجات تناسب المستخدم

أعد الرد بصيغة JSON دائماً.
"""


class AIStylistService:
    """خدمة الـ AI Stylist - تختار التوصيات وتشرح السبب"""

    def __init__(self):
        self.provider = settings.AI_PROVIDER
        self._setup_client()

    def _setup_client(self):
        """إعداد العميل حسب المزود"""
        if self.provider == "groq":
            try:
                from groq import Groq
                self.client = Groq(api_key=settings.GROQ_API_KEY) if settings.GROQ_API_KEY else None
                self.model = "llama-3.3-70b-versatile"  # نموذج قوي ومجاني
            except ImportError:
                logger.warning("Groq library not installed")
                self.client = None

        elif self.provider == "gemini":
            try:
                import google.generativeai as genai
                if settings.GEMINI_API_KEY:
                    genai.configure(api_key=settings.GEMINI_API_KEY)
                    self.client = genai.GenerativeModel("gemini-1.5-flash")
                    self.model = "gemini-1.5-flash"
                else:
                    self.client = None
            except ImportError:
                logger.warning("Google Generative AI library not installed")
                self.client = None

        elif self.provider == "ollama":
            # Ollama يستخدم OpenAI-compatible API
            try:
                from openai import OpenAI
                self.client = OpenAI(
                    base_url=f"{settings.OLLAMA_BASE_URL}/v1",
                    api_key="ollama"  # غير مهم
                )
                self.model = "llama3.2"
            except ImportError:
                self.client = None

    async def recommend_outfit(
        self,
        preferences: dict,
        available_products: list[dict]
    ) -> dict:
        """
        يطلب من الـ AI أفضل توصيات بناءً على تفضيلات المستخدم
        Returns: {
            "recommended_product_ids": [...],
            "outfit": {"Top": id, "Shoes": id, ...},
            "explanation": "..."
        }
        """
        if not self.client:
            # Fallback للـ rule-based لو الـ AI مش متاح
            return self._rule_based_fallback(preferences, available_products)

        # تقليل البيانات المرسلة للـ AI (نرسل بس المهم)
        products_summary = [
            {
                "id": str(p["id"]),
                "title": p["title"],
                "category": p["category"],
                "color": p["color"],
                "brand": p["brand"],
                "price": p["sale_price"],
                "description": p["description"][:150],  # أول 150 حرف فقط
            }
            for p in available_products[:50]  # حد أقصى 50 منتج للـ AI
        ]

        user_prompt = f"""تفضيلات المستخدم:
- النمط: {preferences.get('style')}
- المناسبة: {preferences.get('occasion')}
- نوع الجسم: {preferences.get('body_type')}
- الألوان المفضلة: {', '.join(preferences.get('favorite_colors', []))}
- التصنيفات المفضلة: {', '.join(preferences.get('preferred_categories', []))}

المنتجات المتاحة:
{json.dumps(products_summary, ensure_ascii=False, indent=2)}

أعد JSON بالشكل التالي:
{{
  "recommended_product_ids": ["id1", "id2", ...],
  "outfit": {{
    "Top": "product_id_for_top",
    "Outerwear": "product_id_for_outerwear",
    "Shoes": "product_id_for_shoes",
    "Accessory": "product_id_for_accessory"
  }},
  "explanation": "شرح مختصر بالعربية ليش هذه المنتجات تناسب المستخدم"
}}
"""

        try:
            response_text = await self._call_llm(user_prompt)
            result = self._parse_json_response(response_text)
            return result
        except Exception as e:
            logger.error(f"AI error: {e}")
            return self._rule_based_fallback(preferences, available_products)

    async def _call_llm(self, user_prompt: str) -> str:
        """استدعاء الـ LLM حسب المزود"""
        if self.provider == "groq":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
            )
            return response.choices[0].message.content

        elif self.provider == "gemini":
            response = self.client.generate_content(
                f"{SYSTEM_PROMPT}\n\n{user_prompt}",
                generation_config={"response_mime_type": "application/json"}
            )
            return response.text

        elif self.provider == "ollama":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
            )
            return response.choices[0].message.content

        raise ValueError(f"Unknown provider: {self.provider}")

    def _parse_json_response(self, text: str) -> dict:
        """استخراج JSON من رد الـ AI"""
        # إزالة markdown code blocks لو موجودة
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)

    def _rule_based_fallback(
        self,
        preferences: dict,
        products: list[dict]
    ) -> dict:
        """نظام احتياطي بقواعد بسيطة لو الـ AI مش شغال"""
        scored = []
        for p in products:
            score = 0
            if p["color"] in preferences.get("favorite_colors", []):
                score += 2
            if p["category"] in preferences.get("preferred_categories", []):
                score += 3
            scored.append((p, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_products = [p for p, _ in scored[:10]]

        outfit = {
            "Top": None,
            "Outerwear": None,
            "Shoes": None,
            "Accessory": None,
        }
        for p in top_products:
            cat = p["category"]
            if cat in ["Men", "Women", "Dresses"] and not outfit["Top"]:
                outfit["Top"] = str(p["id"])
            elif cat == "Outerwear" and not outfit["Outerwear"]:
                outfit["Outerwear"] = str(p["id"])
            elif cat == "Shoes" and not outfit["Shoes"]:
                outfit["Shoes"] = str(p["id"])
            elif cat == "Accessories" and not outfit["Accessory"]:
                outfit["Accessory"] = str(p["id"])

        return {
            "recommended_product_ids": [str(p["id"]) for p in top_products],
            "outfit": outfit,
            "explanation": "اخترنا هذه القطع بناءً على ألوانك المفضلة والتصنيفات اللي تهتم فيها."
        }


# Singleton
ai_stylist = AIStylistService()
