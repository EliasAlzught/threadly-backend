"""
Auth endpoints - signup, login, social login
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
from app.schemas import UserSignUp, UserLogin, Token, UserOut
from app.core.security import hash_password, verify_password, create_access_token
from app.api.deps import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=Token, status_code=status.HTTP_201_CREATED)
def signup(data: UserSignUp, db: Session = Depends(get_db)):
    """تسجيل مستخدم جديد"""
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )

    user = User(
        email=data.email,
        name=data.name,
        phone=data.phone,
        hashed_password=hash_password(data.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id))
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post("/login", response_model=Token)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """تسجيل الدخول"""
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_access_token(subject=str(user.id))
    return Token(access_token=token, user=UserOut.model_validate(user))


@router.post("/login/form", response_model=Token)
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    تسجيل دخول بصيغة OAuth2 form - يجعل زر Authorize في Swagger يعمل.

    ملاحظة: ضع *الإيميل* في خانة username.
    هذه النسخة تستقبل form-encoded (username/password) بينما تستقبل النسخة
    أعلاه JSON (email/password). كلاهما يرجع نفس التوكن.
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_access_token(subject=str(user.id))
    return Token(access_token=token, user=UserOut.model_validate(user))
def get_me(current_user: User = Depends(get_current_user)):
    """الحصول على بيانات المستخدم الحالي"""
    return current_user


# TODO: إضافة social login (Google, Apple, Facebook)
# ستحتاج لـ:
# - تسجيل التطبيق في Google Cloud Console / Apple Developer / Facebook Developers
# - التحقق من الـ ID token المرسل من الفرونت إند
# - إنشاء أو تحديث المستخدم في قاعدة البيانات
