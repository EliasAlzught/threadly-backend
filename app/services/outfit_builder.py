"""
خدمة بناء الأطقم (Outfit Builder)

تستخدم الـ AI (Groq) لاختيار قطع متناسقة تشكّل طقم كامل.
لو الـ AI غير متاح أو فشل، يرجع لخوارزمية بسيطة (rule-based fallback).

المنطق:
1. نجمع المنتجات المتاحة مقسّمة حسب الـ slot
2. نطلب من الـ AI يختار قطعة لكل خانة مطلوبة بحيث تكون متناسقة
3. fallback: نختار حسب تطابق اللون والسعر
"""
import json
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# الخانات الأساسية لطقم كامل
DEFAULT_SLOTS = ["top", "bottom", "shoes", "accessory"]

OUTFIT_SYSTEM_PROMPT = """أنت خبير تنسيق أزياء لتطبيق Threadly.
مهمتك بناء طقم ملابس متناسق ومتكامل من المنتجات المتاحة.

قواعد التنسيق:
- الألوان يجب أن تتناغم (متطابقة أو متكاملة)
- القطع تناسب المناسبة المطلوبة
- لا تختار قطعتين لنفس الخانة
- احترم الميزانية لو محددة

أعد JSON دائماً بدون أي نص إضافي.
"""


class OutfitBuilderService:
    """خدمة بناء الأطقم المتناسقة"""

    def __init__(self):
        self.provider = settings.AI_PROVIDER
        self.client = None
        self.model = None
        self._setup()

    def _setup(self):
        if self.provider == "groq":
            try:
                from groq import Groq
                if settings.GROQ_API_KEY:
                    self.client = Groq(api_key=settings.GROQ_API_KEY)
                    self.model = "llama-3.3-70b-versatile"
            except ImportError:
                logger.warning("Groq not installed")
        elif self.provider == "gemini":
            try:
                import google.generativeai as genai
                if settings.GEMINI_API_KEY:
                    genai.configure(api_key=settings.GEMINI_API_KEY)
                    self.client = genai.GenerativeModel("gemini-1.5-flash")
                    self.model = "gemini-1.5-flash"
            except ImportError:
                logger.warning("Gemini not installed")

    def build_outfit(
        self,
        request: dict,
        available_products: list[dict],
    ) -> dict:
        """
        يبني طقم كامل.

        request: {occasion, style, favorite_colors, budget_max, required_slots, gender}
        available_products: قائمة المنتجات [{id, title, slot, color, price, ...}]

        Returns: {
          "name": str,
          "description": str,
          "items": { slot: product_id },  # خانة → معرّف منتج
        }
        """
        required_slots = request.get("required_slots") or DEFAULT_SLOTS

        # تقسيم المنتجات حسب الخانة
        by_slot: dict[str, list] = {}
        for p in available_products:
            slot = p.get("slot")
            if slot:
                by_slot.setdefault(slot, []).append(p)

        # لو ما فيه AI، نروح للـ fallback مباشرة
        if not self.client:
            return self._rule_based(request, by_slot, required_slots)

        try:
            return self._ai_build(request, by_slot, required_slots)
        except Exception as e:
            logger.error(f"AI outfit build failed: {e}")
            return self._rule_based(request, by_slot, required_slots)

    def _ai_build(self, request: dict, by_slot: dict, required_slots: list) -> dict:
        """بناء الطقم بالـ AI"""
        # نجهّز ملخص مختصر للمنتجات (نوفّر tokens)
        catalog = {}
        for slot in required_slots:
            items = by_slot.get(slot, [])[:15]  # حد أقصى 15 لكل خانة
            catalog[slot] = [
                {
                    "id": str(p["id"]),
                    "title": p["title"],
                    "color": p["color"],
                    "price": p["sale_price"],
                    "brand": p["brand"],
                }
                for p in items
            ]

        budget = request.get("budget_max")
        budget_line = f"\n- الميزانية القصوى للطقم: ${budget}" if budget else ""

        prompt = f"""ابنِ طقم ملابس متناسق:
- المناسبة: {request.get('occasion')}
- النمط: {request.get('style') or 'غير محدد'}
- الألوان المفضلة: {', '.join(request.get('favorite_colors', [])) or 'غير محدد'}{budget_line}

المنتجات المتاحة لكل خانة:
{json.dumps(catalog, ensure_ascii=False, indent=2)}

اختر قطعة واحدة لكل خانة بحيث يكون الطقم متناسقاً.
أعد JSON بالشكل:
{{
  "name": "اسم جذّاب للطقم بالعربية",
  "description": "شرح مختصر ليش هذا الطقم متناسق",
  "items": {{
    "top": "معرّف_المنتج",
    "bottom": "معرّف_المنتج",
    "shoes": "معرّف_المنتج",
    "accessory": "معرّف_المنتج"
  }}
}}
ضع فقط الخانات المتوفّرة. لا تخترع معرّفات."""

        text = self._call_llm(prompt)
        result = self._parse_json(text)

        # تنظيف: نتأكد إن المعرّفات صحيحة وموجودة فعلاً
        valid_ids = {str(p["id"]) for items in by_slot.values() for p in items}
        cleaned_items = {}
        for slot, pid in result.get("items", {}).items():
            if pid and str(pid) in valid_ids:
                cleaned_items[slot] = str(pid)

        # لو الـ AI فوّت خانات، نكمّلها بالـ fallback
        for slot in required_slots:
            if slot not in cleaned_items and by_slot.get(slot):
                cleaned_items[slot] = str(by_slot[slot][0]["id"])

        return {
            "name": result.get("name", "إطلالة منسّقة"),
            "description": result.get("description", ""),
            "items": cleaned_items,
        }

    def _call_llm(self, prompt: str) -> str:
        if self.provider == "groq":
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": OUTFIT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.7,
            )
            return resp.choices[0].message.content
        elif self.provider == "gemini":
            resp = self.client.generate_content(
                f"{OUTFIT_SYSTEM_PROMPT}\n\n{prompt}",
                generation_config={"response_mime_type": "application/json"},
            )
            return resp.text
        raise ValueError(f"Unsupported provider: {self.provider}")

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)

    def _rule_based(self, request: dict, by_slot: dict, required_slots: list) -> dict:
        """
        خوارزمية احتياطية بسيطة (لو الـ AI مش متاح).
        تختار لكل خانة القطعة الأفضل حسب:
        - تطابق اللون مع المفضّلة (+points)
        - ضمن الميزانية
        - الأرخص يفوز عند التساوي
        """
        favorite_colors = [c.lower() for c in request.get("favorite_colors", [])]
        budget = request.get("budget_max")

        items = {}
        for slot in required_slots:
            candidates = by_slot.get(slot, [])
            if not candidates:
                continue

            best = None
            best_score = -1
            for p in candidates:
                score = 0
                # تطابق اللون
                if p.get("color", "").lower() in favorite_colors:
                    score += 10
                # ضمن الميزانية
                if budget and p.get("sale_price", 0) <= budget / len(required_slots):
                    score += 5
                # تفضيل الأرخص
                score += max(0, 5 - p.get("sale_price", 0) / 50)

                if score > best_score:
                    best_score = score
                    best = p

            if best:
                items[slot] = str(best["id"])

        occasion = request.get("occasion", "")
        return {
            "name": f"إطلالة {occasion}" if occasion else "إطلالة منسّقة",
            "description": "طقم منسّق حسب ألوانك المفضّلة وميزانيتك.",
            "items": items,
        }


# نسخة واحدة مشتركة
outfit_builder = OutfitBuilderService()
