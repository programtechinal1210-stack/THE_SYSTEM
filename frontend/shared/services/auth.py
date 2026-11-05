# shared/services/auth.py
# ============================================================
# خدمة المصادقة المشتركة
# ============================================================

from .api_client import ApiClient, ApiException, UnauthorizedException


class AuthService:
    """خدمة المصادقة المشتركة - تغليف ApiClient"""
    
    def __init__(self):
        self.client = ApiClient()
    
    def login(self, username: str, password: str) -> dict:
        """
        تسجيل الدخول
        
        Returns:
        - dict: {'access_token': ..., 'user': {...}}
        """
        response = self.client.post(
            "/auth/login",
            data={"username": username, "password": password},
            include_auth=False
        )
        
        # تخزين التوكن
        access_token = response.get('access_token')
        if access_token:
            self.client.set_token(access_token)
        
        return response
    
    def logout(self):
        """تسجيل الخروج"""
        try:
            self.client.post("/auth/logout")
        except:
            pass
        self.client.clear_token()
    
    def register(self, user_data: dict) -> dict:
        """تسجيل مستخدم جديد"""
        return self.client.post(
            "/auth/register",
            data=user_data,
            include_auth=False
        )
    
    def get_current_user(self) -> dict:
        """جلب بيانات المستخدم الحالي"""
        return self.client.get("/auth/me")
    
    def refresh_token(self, refresh_token: str) -> dict:
        """تجديد التوكن"""
        return self.client.post(
            "/auth/refresh",
            data={"refresh_token": refresh_token},
            include_auth=False
        )
