"""
مدير الاتصالات اللحظية (WebSocket) - مشترك بين الشات والإشعارات.

لماذا مشترك؟
كان لكل من الشات والإشعارات اتصال منفصل سيتطلب من العميل فتح أكثر من socket.
بجعل المدير واحداً (singleton)، يفتح الـ Flutter اتصالاً واحداً على /api/ws
ويستقبل عليه الرسائل والإشعارات معاً، كلٌّ بنوعه (type).

يدعم اتصالات متعددة لنفس المستخدم (هاتف + ويب مثلاً).

ملاحظة مهمة عن التزامن:
معظم نقاط النهاية هنا متزامنة (def عادية تعمل في threadpool) بينما إرسال
WebSocket غير متزامن (يحتاج event loop). لذلك نلتقط حلقة الأحداث الرئيسية
عند الإقلاع ونوفّر دالة dispatch() متزامنة تجدول الإرسال على تلك الحلقة
بأمان من أي خيط (fire-and-forget).
"""
import asyncio
from typing import Dict, Optional, Set
from fastapi import WebSocket


class ConnectionManager:
    """يدير الاتصالات المفتوحة - عدة اتصالات لكل مستخدم."""

    def __init__(self) -> None:
        # user_id -> مجموعة من اتصالات WebSocket
        self._connections: Dict[str, Set[WebSocket]] = {}
        # حلقة الأحداث الرئيسية (تُضبط عند الإقلاع)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """يُستدعى مرة واحدة عند إقلاع التطبيق."""
        self._loop = loop

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(str(user_id), set()).add(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket) -> None:
        conns = self._connections.get(str(user_id))
        if not conns:
            return
        conns.discard(websocket)
        if not conns:
            self._connections.pop(str(user_id), None)

    def is_online(self, user_id: str) -> bool:
        return bool(self._connections.get(str(user_id)))

    async def send_to_user(self, user_id: str, message: dict) -> bool:
        """
        يرسل رسالة JSON لكل اتصالات المستخدم.
        يرجع True لو وصلت لاتصال واحد على الأقل.
        يزيل أي اتصال ميت تلقائياً.
        """
        conns = list(self._connections.get(str(user_id), set()))
        if not conns:
            return False

        delivered = False
        for ws in conns:
            try:
                await ws.send_json(message)
                delivered = True
            except Exception:
                self.disconnect(str(user_id), ws)
        return delivered

    def dispatch(self, user_id: str, message: dict) -> None:
        """
        إرسال متزامن وآمن من أي خيط (fire-and-forget).
        يصلح للاستدعاء من نقاط النهاية المتزامنة (sync) دون انتظار النتيجة.
        لو لا يوجد متصل أو لم تُضبط الحلقة بعد، يتجاهل بهدوء.
        """
        if self._loop is None:
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self.send_to_user(str(user_id), message), self._loop
            )
        except Exception:
            # الإرسال اللحظي best-effort - لا يجب أن يُفشل أي عملية أساسية
            pass


# نسخة واحدة مشتركة في كل التطبيق
manager = ConnectionManager()
