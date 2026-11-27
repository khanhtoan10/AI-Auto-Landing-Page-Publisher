import time
import bcrypt
import pymysql
from fastapi import APIRouter, Depends, HTTPException, Request, status
from passlib.context import CryptContext

from core.config import settings
from core.security import create_access_token, get_current_user
from schemas.auth import LoginRequest, UserRegisterRequest, UserRegisterResponse, UserResponse

router = APIRouter(prefix="/auth", tags=["Auth"])

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Xác thực mật khẩu an toàn bằng bcrypt trực tiếp (khắc phục lỗi passlib trên bcrypt 4.x)."""
    try:
        return bcrypt.checkpw(
            str(plain_password).encode("utf-8")[:72],
            str(hashed_password).encode("utf-8"),
        )
    except Exception:
        try:
            return pwd_context.verify(str(plain_password)[:72], hashed_password)
        except Exception:
            return False


def hash_password(password: str) -> str:
    """Mã hoá mật khẩu an toàn bằng bcrypt trực tiếp."""
    try:
        return bcrypt.hashpw(
            str(password).encode("utf-8")[:72],
            bcrypt.gensalt(),
        ).decode("utf-8")
    except Exception:
        return pwd_context.hash(str(password)[:72])

# ── Cấu hình chống đăng nhập sai liên tiếp (Brute-force Protection) ──
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_WINDOW_SECONDS = 15 * 60  # Khóa 15 phút nếu sai quá 5 lần
_failed_login_tracker: dict[str, dict] = {}


def _get_login_keys(request: Request, email: str) -> tuple[str, str]:
    client_ip = request.client.host if request.client else "unknown"
    norm_email = email.strip().lower()
    return f"email:{norm_email}", f"ip:{client_ip}:{norm_email}"


def _check_login_rate_limit(keys: tuple[str, str]) -> None:
    now = time.time()
    for key in keys:
        record = _failed_login_tracker.get(key)
        if not record:
            continue
        locked_until = record.get("locked_until", 0)
        if locked_until > now:
            remaining_minutes = max(1, int((locked_until - now + 59) // 60))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "success": False,
                    "error": {
                        "code": "TOO_MANY_LOGIN_ATTEMPTS",
                        "message": f"Bạn đã đăng nhập sai quá {MAX_LOGIN_ATTEMPTS} lần. Vui lòng thử lại sau {remaining_minutes} phút.",
                        "details": [],
                    },
                },
            )
        if now - record.get("first_attempt_at", now) > LOCKOUT_WINDOW_SECONDS:
            _failed_login_tracker.pop(key, None)


def _record_failed_login(keys: tuple[str, str]) -> int:
    now = time.time()
    remaining_tries = MAX_LOGIN_ATTEMPTS
    for key in keys:
        record = _failed_login_tracker.get(key)
        if not record or (now - record["first_attempt_at"] > LOCKOUT_WINDOW_SECONDS):
            record = {"count": 1, "first_attempt_at": now, "locked_until": 0}
        else:
            record["count"] += 1

        if record["count"] >= MAX_LOGIN_ATTEMPTS:
            record["locked_until"] = now + LOCKOUT_WINDOW_SECONDS
            remaining_tries = 0
        else:
            remaining_tries = min(remaining_tries, MAX_LOGIN_ATTEMPTS - record["count"])

        _failed_login_tracker[key] = record
    return remaining_tries


def _clear_failed_login(keys: tuple[str, str]) -> None:
    for key in keys:
        _failed_login_tracker.pop(key, None)


def get_db_connection():
    return pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


# 1. Đăng ký
@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserRegisterResponse)
async def register_user(payload: UserRegisterRequest):
    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu phải có tối thiểu 8 ký tự",
        )

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM users WHERE email = %s", (payload.email,))
            if cursor.fetchone():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email này đã được sử dụng trên hệ thống",
                )

            clean_pwd = str(payload.password)[:72]
            hashed_pwd = hash_password(clean_pwd)

            insert_query = """
            INSERT INTO users (full_name, email, hashed_password)
            VALUES (%s, %s, %s)
            """
            cursor.execute(insert_query, (payload.full_name, payload.email, hashed_pwd))
            new_user_id = cursor.lastrowid

            return UserRegisterResponse(
                id=new_user_id,
                full_name=payload.full_name,
                email=payload.email,
                message="Đăng ký tài khoản thành công!",
            )
    finally:
        connection.close()


# 2. Đăng nhập trả JWT access token (có giới hạn số lần đăng nhập sai)
@router.post("/login", status_code=status.HTTP_200_OK)
async def login(payload: LoginRequest, request: Request):
    login_keys = _get_login_keys(request, payload.email)
    _check_login_rate_limit(login_keys)

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id, email, hashed_password FROM users WHERE email = %s",
                (payload.email,),
            )
            user = cursor.fetchone()

            clean_pwd = str(payload.password)[:72]
            if not user or not verify_password(clean_pwd, user["hashed_password"]):
                remaining = _record_failed_login(login_keys)
                if remaining == 0:
                    msg = f"Bạn đã đăng nhập sai quá {MAX_LOGIN_ATTEMPTS} lần. Tài khoản tạm khóa trong 15 phút."
                    status_code = status.HTTP_429_TOO_MANY_REQUESTS
                    err_code = "TOO_MANY_LOGIN_ATTEMPTS"
                else:
                    msg = f"Email hoặc mật khẩu không chính xác (còn {remaining} lần thử)."
                    status_code = status.HTTP_401_UNAUTHORIZED
                    err_code = "INVALID_CREDENTIALS"

                raise HTTPException(
                    status_code=status_code,
                    detail={
                        "success": False,
                        "error": {
                            "code": err_code,
                            "message": msg,
                            "details": [],
                        },
                    },
                )

            _clear_failed_login(login_keys)
            access_token = create_access_token(
                data={"sub": str(user["id"]), "email": user["email"]}
            )
            return {
                "success": True,
                "data": {
                    "access_token": access_token,
                    "token_type": "bearer",
                },
            }
    finally:
        connection.close()


# 3. Lấy thông tin cá nhân qua dependency dùng chung get_current_user
@router.get("/me", status_code=status.HTTP_200_OK)
async def get_me(current_user: dict = Depends(get_current_user)):
    return {
        "success": True,
        "data": UserResponse(**current_user).model_dump(),
    }