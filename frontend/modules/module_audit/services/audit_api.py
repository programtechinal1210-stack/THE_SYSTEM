import requests
import sys
from pathlib import Path
# استيراد ApiClient من shared.services
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent / 'shared' / 'services'))
from api_client import ApiClient
api_client = ApiClient()
API_BASE = api_client.base_url.rstrip('/')
import json
import os

# API_BASE مستورد من api_client
TOKEN_FILE = os.path.join(os.path.dirname(__file__), ".audit_token.json")

def get_admin_token():
    """Legacy automatic admin login is intentionally disabled."""
    return None

def get_headers():
    token = get_admin_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"} if token else {"Content-Type": "application/json"}

def safe_request(url, params=None):
    try:
        r = requests.get(url, params=params, headers=get_headers(), timeout=15)
        if r.ok:
            try: return r.json()
            except: pass
        if r.status_code == 401 and os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
            r = requests.get(url, params=params, headers=get_headers(), timeout=15)
            if r.ok:
                try: return r.json()
                except: pass
        return {"items": [], "total": 0}
    except: return {"items": [], "total": 0}

def safe_items(data):
    if isinstance(data, list): return data
    if isinstance(data, dict): return data.get("items", [])
    return []

_users_cache = None
def get_users_map():
    global _users_cache
    if _users_cache: return _users_cache
    try:
        data = safe_request(f"{API_BASE}/users/", {"limit": 500})
        items = safe_items(data)
        _users_cache = {u["id"]: u.get("full_name", u.get("username", "?")) for u in items if "id" in u}
        return _users_cache
    except: return {}

def get_audit_logs(request=None):
    data = safe_request(f"{API_BASE}/audit/logs", {"limit": 100000, "skip": 0})
    items = safe_items(data)
    users = get_users_map()
    for item in items:
        uid = item.get("user_id")
        item["user_name"] = users.get(uid, str(uid)[:8] if uid else "النظام")
    return {"results": items, "total_count": len(items)}

def get_audit_summary(request=None):
    data = safe_request(f"{API_BASE}/audit/stats/summary")
    try:
        if isinstance(data, dict):
            return {"total_actions": data.get("total_actions",0), "unique_users": data.get("unique_users",0), "pending_followups": data.get("pending_followups",0), "open_anomalies": data.get("open_anomalies",0)}
    except: pass
    return {"total_actions":0,"unique_users":0,"pending_followups":0,"open_anomalies":0}

def get_followups(request=None): return {"results": []}
def get_anomalies(request=None): return {"results": []}
def get_alerts(request=None): return {"results": []}
def get_execution(request=None): return {"results": []}
def get_exports(request=None): return {"results": []}
