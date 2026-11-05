from fastapi import Request, HTTPException, status

def get_current_user(request: Request):
  #  \"\"\"الحصول على المستخدم الحالي من request.state (يتم تعيينه بواسطة AuthMiddleware)\"\"\"
    user = getattr(request.state, "user", None)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="غير مصرح به - يرجى تسجيل الدخول"
        )

    return user
