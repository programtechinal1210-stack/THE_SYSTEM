# shared/services/api_client.py
# ============================================================
# عميل HTTP موحد للتواصل مع FastAPI Backend
# ============================================================

import requests
import json
import logging
from typing import Optional, Dict, Any, List
from django.conf import settings
from core.request_context import current_session

logger = logging.getLogger(__name__)


class ApiException(Exception):
    pass

class UnauthorizedException(ApiException):
    pass

class ForbiddenException(ApiException):
    pass

class NotFoundException(ApiException):
    pass

class ConflictException(ApiException):
    pass

class ValidationException(ApiException):
    pass


class ApiClient:
    
    def __init__(self, token: Optional[str] = None):
        self.base_url = settings.API_BASE_URL.rstrip("/")  # ثابت - Backend API
        self.timeout = 10
        self._token = token
    
    @property
    def token(self) -> Optional[str]:
        if self._token is not None:
            return self._token
        active = current_session()
        return active.get("access_token") if active is not None else None
    
    @token.setter
    def token(self, value: str):
        self._token = value
    
    def set_token(self, token: str):
        self._token = token
    
    def clear_token(self):
        self._token = ""
    
    def is_authenticated(self) -> bool:
        return bool(self.token)
    
    def _get_headers(self, include_auth: bool = True) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if include_auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers
    
    def _build_url(self, endpoint: str) -> str:
        """بناء الرابط الكامل - مع المنفذ 8001"""
        # إزالة /api/v1 إذا كان موجوداً في الـ endpoint
        if endpoint.startswith('/api/v1/'):
            endpoint = endpoint[7:]
        
        # التأكد من وجود / في البداية
        if not endpoint.startswith('/'):
            endpoint = '/' + endpoint
        
        # base_url يحتوي على http://127.0.0.1:8001/api/v1
        url = f"{self.base_url}{endpoint}"
        return url
    
    def _handle_response(self, response: requests.Response) -> Any:
        if response.status_code == 204:
            return {}
        
        content_type = response.headers.get('content-type', '')
        
        # إذا كانت الاستجابة HTML (خطأ في التوجيه)
        if 'text/html' in content_type:
            raise ApiException(f"الخادم أرجع HTML بدلاً من JSON. تأكد أن base_url صحيح: {self.base_url}")
        
        try:
            data = response.json()
        except json.JSONDecodeError:
            raise ApiException("استجابة غير صالحة من الخادم")
        
        if 200 <= response.status_code < 300:
            return data
        
        detail = data.get('detail', 'حدث خطأ غير معروف')
        
        if response.status_code == 401:
            raise UnauthorizedException(detail)
        elif response.status_code == 403:
            raise ForbiddenException(detail)
        elif response.status_code == 404:
            raise NotFoundException(detail)
        elif response.status_code == 409:
            raise ConflictException(detail)
        elif response.status_code == 422:
            raise ValidationException(detail)
        else:
            raise ApiException(detail)
    
    def _request(self, method, endpoint, data=None, params=None, include_auth=True):
        try:
            response = requests.request(method, self._build_url(endpoint),
                headers=self._get_headers(include_auth), json=data, params=params, timeout=self.timeout)
            active = current_session()
            if (response.status_code == 401 and include_auth and active is not None
                    and active.get("refresh_token") and self.token == active.get("access_token")
                    and endpoint not in ("/auth/refresh", "/auth/logout")):
                refreshed = requests.post(self._build_url("/auth/refresh"),
                    json={"refresh_token": active["refresh_token"]}, timeout=self.timeout)
                if refreshed.status_code == 200:
                    tokens = refreshed.json()
                    active.update({key: tokens[key] for key in ("access_token", "refresh_token")})
                    self._token = tokens["access_token"]
                    response = requests.request(method, self._build_url(endpoint),
                        headers=self._get_headers(), json=data, params=params, timeout=self.timeout)
            return self._handle_response(response)
        except requests.RequestException:
            raise ApiException("Connection to the server failed") from None

    def get(self, endpoint, params=None, include_auth=True):
        return self._request("GET", endpoint, params=params, include_auth=include_auth)

    def download(self, endpoint, params=None):
        try:
            response = requests.get(
                self._build_url(endpoint),
                headers=self._get_headers(),
                params=params,
                timeout=self.timeout,
            )
            active = current_session()
            if (response.status_code == 401 and active is not None
                    and active.get("refresh_token") and self.token == active.get("access_token")):
                refreshed = requests.post(
                    self._build_url("/auth/refresh"),
                    json={"refresh_token": active["refresh_token"]},
                    timeout=self.timeout,
                )
                if refreshed.status_code == 200:
                    tokens = refreshed.json()
                    active.update({key: tokens[key] for key in ("access_token", "refresh_token")})
                    self._token = tokens["access_token"]
                    response = requests.get(
                        self._build_url(endpoint),
                        headers=self._get_headers(),
                        params=params,
                        timeout=self.timeout,
                    )
            if not 200 <= response.status_code < 300:
                self._handle_response(response)
            return (
                response.content,
                response.headers.get("content-type", "application/octet-stream"),
                response.headers.get("content-disposition", ""),
            )
        except requests.RequestException:
            raise ApiException("Connection to the server failed") from None

    def post(self, endpoint, data=None, include_auth=True):
        return self._request("POST", endpoint, data=data or {}, include_auth=include_auth)

    def put(self, endpoint, data=None, include_auth=True):
        return self._request("PUT", endpoint, data=data or {}, include_auth=include_auth)

    def patch(self, endpoint, data=None, include_auth=True):
        return self._request("PATCH", endpoint, data=data or {}, include_auth=include_auth)

    def delete(self, endpoint, include_auth=True):
        self._request("DELETE", endpoint, include_auth=include_auth)
        return True


api_client = ApiClient()
