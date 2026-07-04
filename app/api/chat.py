"""
Chat endpoints - REST + WebSocket

التحسينات:
- يستخدم مدير الاتصالات المشترك (services/realtime) - نفس السوكِت يحمل
  الرسائل والإشعارات معاً.
- يُنشئ إشعاراً عند كل رسالة جديدة (يصل حتى لو المستلم غير متصل).
- يحدّث updated_at للمحادثة عند كل رسالة (للترتيب الصحيح).
- يمنع مراسلة النفس.
"""
import json
from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.db.session import get_db, SessionLocal
from app.models import ChatThread, ChatMessage, User, NotificationType
from app.schemas import MessageCreate, MessageOut
from app.api.deps import get_current_user
from app.core.security import decode_token
from app.services.realtime import manager
from app.services.notifications import notify

router = APIRouter(prefix="/chat", tags=["Chat"])


# ============ REST Endpoints ============

@router.get("/threads")
def get_threads(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """قائمة المحادثات الخاصة بالمستخدم"""
    threads = db.query(ChatThread).filter(
        or_(
            ChatThread.user1_id == current_user.id,
            ChatThread.user2_id == current_user.id,
        )
    ).order_by(ChatThread.updated_at.desc()).all()

    result = []
    for t in threads:
        # الطرف الآخر في المحادثة
        other_id = t.user2_id if t.user1_id == current_user.id else t.user1_id
        other = db.query(User).filter(User.id == other_id).first()

        last_msg = db.query(ChatMessage).filter(
            ChatMessage.thread_id == t.id
        ).order_by(ChatMessage.created_at.desc()).first()

        unread_count = db.query(ChatMessage).filter(
            and_(
                ChatMessage.thread_id == t.id,
                ChatMessage.sender_id != current_user.id,
                ChatMessage.is_read == False,
            )
        ).count()

        result.append({
            "id": str(t.id),
            "other_user_id": str(other.id) if other else None,
            "other_user_name": other.name if other else "Unknown",
            "other_user_avatar": other.avatar_url if other else None,
            "product_id": str(t.product_id) if t.product_id else None,
            "last_message": last_msg.content if last_msg else None,
            "last_message_at": last_msg.created_at.isoformat() if last_msg else None,
            "unread_count": unread_count,
        })

    return result


@router.get("/threads/{thread_id}/messages", response_model=list[MessageOut])
def get_messages(
    thread_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """رسائل محادثة محددة"""
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id).first()
    if not thread:
        raise HTTPException(404, "Thread not found")
    if current_user.id not in [thread.user1_id, thread.user2_id]:
        raise HTTPException(403, "Not authorized")

    # علّم الرسائل كمقروءة
    db.query(ChatMessage).filter(
        and_(
            ChatMessage.thread_id == thread_id,
            ChatMessage.sender_id != current_user.id,
            ChatMessage.is_read == False,
        )
    ).update({"is_read": True})
    db.commit()

    return thread.messages


@router.post("/messages", response_model=MessageOut)
async def send_message(
    data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """إرسال رسالة - ينشئ المحادثة لو غير موجودة"""
    # ابحث عن المحادثة أو أنشئها
    if data.thread_id:
        thread = db.query(ChatThread).filter(ChatThread.id == data.thread_id).first()
        if not thread:
            raise HTTPException(404, "Thread not found")
        # تأكد أن المرسل طرف في المحادثة
        if current_user.id not in (thread.user1_id, thread.user2_id):
            raise HTTPException(403, "Not authorized for this thread")
    else:
        if not data.recipient_id:
            raise HTTPException(400, "recipient_id required for new thread")

        # منع مراسلة النفس
        if data.recipient_id == current_user.id:
            raise HTTPException(400, "You cannot message yourself")

        # تأكد أن المستلم موجود
        recipient = db.query(User).filter(User.id == data.recipient_id).first()
        if not recipient:
            raise HTTPException(404, "Recipient not found")

        # ابحث عن محادثة موجودة
        thread = db.query(ChatThread).filter(
            or_(
                and_(
                    ChatThread.user1_id == current_user.id,
                    ChatThread.user2_id == data.recipient_id,
                ),
                and_(
                    ChatThread.user1_id == data.recipient_id,
                    ChatThread.user2_id == current_user.id,
                ),
            )
        ).first()

        if not thread:
            thread = ChatThread(
                user1_id=current_user.id,
                user2_id=data.recipient_id,
                product_id=data.product_id,
            )
            db.add(thread)
            db.flush()

    # أنشئ الرسالة
    message = ChatMessage(
        thread_id=thread.id,
        sender_id=current_user.id,
        content=data.content,
    )
    db.add(message)
    # حدّث وقت المحادثة لترتيبها بشكل صحيح في القائمة
    thread.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(message)

    recipient_id = (
        thread.user2_id if thread.user1_id == current_user.id else thread.user1_id
    )

    # دفعة لحظية للرسالة (لو المستلم متصل) عبر السوكِت المشترك
    manager.dispatch(
        str(recipient_id),
        {
            "type": "new_message",
            "thread_id": str(thread.id),
            "message": {
                "id": str(message.id),
                "sender_id": str(message.sender_id),
                "content": message.content,
                "created_at": message.created_at.isoformat(),
            },
        },
    )

    # إشعار دائم (يظهر في قائمة الإشعارات حتى لو كان المستلم غير متصل)
    preview = data.content if len(data.content) <= 80 else data.content[:77] + "..."
    notify(
        db, recipient_id,
        type=NotificationType.NEW_MESSAGE,
        title=f"New message from {current_user.name}",
        message=preview,
        data={
            "thread_id": str(thread.id),
            "sender_id": str(current_user.id),
            "sender_name": current_user.name,
        },
    )

    return message


# ============ WebSocket Endpoint ============

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """
    WebSocket للـ real-time.
    استخدمه من Flutter: ws://localhost:8000/api/chat/ws?token=<JWT>

    يستقبل عليه نوعين من الرسائل:
    - {"type": "new_message", ...}    رسائل الشات
    - {"type": "notification", ...}   الإشعارات (طلبات، اشتراك...)
    """
    # التحقق من التوكن
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=1008, reason="Invalid token")
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=1008, reason="Invalid token")
        return

    await manager.connect(user_id, websocket)
    try:
        while True:
            # استقبل رسائل من العميل (heartbeat/ping مثلاً)
            await websocket.receive_text()
            # حالياً نتجاهلها - الرسائل تُرسل عبر REST
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception:
        manager.disconnect(user_id, websocket)
