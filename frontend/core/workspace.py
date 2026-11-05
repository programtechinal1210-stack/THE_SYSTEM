"""Server-rendered Core pages using existing Django shell and FastAPI services."""
import json
from urllib.parse import quote
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.contrib import messages
from shared.services.api_client import ApiClient, ApiException, ForbiddenException, UnauthorizedException
from core.ude_05_flags import use_pilot


def _ordered_tree(items):
    by_id = {item["id"]: item for item in items}
    children = {}
    for item in items:
        parent = item.get("parent_id")
        children.setdefault(parent if parent in by_id else None, []).append(item)
    ordered, visited = [], set()
    pending = [(item, 0) for item in reversed(children.get(None, []))]
    while pending:
        item, depth = pending.pop()
        if item["id"] in visited:
            continue
        visited.add(item["id"])
        item["depth"] = depth
        ordered.append(item)
        pending.extend((child, depth + 1) for child in reversed(children.get(item["id"], [])))
    return ordered


def page(request, section):
    client = ApiClient(token=request.session.get("access_token"))
    context = {"section": section, "items": [], "page_title": {
        "home": "الرئيسية", "units": "الهيكل التنظيمي", "users": "المستخدمون",
        "roles": "الأدوار والصلاحيات", "settings": "الإعدادات", "notifications": "الإشعارات",
        "audit": "سجل التدقيق", "profile": "الملف الشخصي", "entities": "دليل الجهات والكيانات"}[section]}
    try:
        identity = client.get("/auth/me")
        request.core_identity = identity
        request.core_modules = client.get("/modules")
        context["identity"] = identity
        context["can_view_users"] = identity.get("is_admin") or "core.users.view" in identity.get("permissions", [])
        context["can_manage"] = identity.get("is_admin") or "core." + {"units": "organizations", "entities": "organizations"}.get(section, section) + ".manage" in identity.get("permissions", [])
        if request.method == "POST":
            perform(request, client, section)
            messages.success(request, "تم حفظ العملية بنجاح")
            return redirect(request.path)
        if section == "home":
            context["activity"] = client.get("/profile/activity")
            context["unread"] = client.get("/notifications/unread-count")["count"]
            # Pass only the allow-listed visual settings to the authenticated Pilot.
            # Tokens and session credentials never enter the rendered page.
            try:
                effective = client.get("/user-settings/effective")
                rows = effective if isinstance(effective, list) else effective.get("effective", [])
                values = {row.get("setting_key"): row.get("value") for row in rows if isinstance(row, dict)}
                context["ude_theme_bootstrap"] = {"settings": {
                    "theme": values.get("core.ude.theme", values.get("theme", "light")),
                    "palette": values.get("core.ude.palette", values.get("ude.palette", values.get("palette", "navy"))),
                    "density": values.get("core.ude.density", values.get("density", "comfortable")),
                    "fontSize": values.get("core.font_size", values.get("font_size", 16)),
                    "fontFamily": values.get("core.ude.font_family", "Tajawal"),
                    "contrast": values.get("core.ude.contrast", "normal")
                }}
            except (ApiException, AttributeError, TypeError):
                context["ude_theme_bootstrap"] = {"settings": {"theme": "light", "palette": "navy", "density": "comfortable", "fontSize": 16, "fontFamily": "Tajawal", "contrast": "normal"}}
        elif section == "units":
            context["items"] = client.get("/org-units/tree")
            by_id = {item["id"]: item for item in context["items"]}
            for item in context["items"]:
                item["parent_name"] = by_id.get(item.get("parent_id"), {}).get("name", "—")
            # Render an ordered hierarchy while retaining scoped orphan roots.
            children = {}
            for item in context["items"]:
                parent = item.get("parent_id")
                children.setdefault(parent if parent in by_id else None, []).append(item)
            ordered, visited = [], set()
            pending = [(item, 0) for item in reversed(children.get(None, []))]
            while pending:
                item, depth = pending.pop()
                if item["id"] in visited:
                    continue
                visited.add(item["id"])
                item["depth"] = depth
                ordered.append(item)
                pending.extend((child, depth + 1) for child in reversed(children.get(item["id"], [])))
            context["tree_nodes"] = ordered
            context["entities"] = client.get("/entities")
            context["entity_types"] = client.get("/entities/entity-types")
            entity_by_id = {item["id"]: item for item in context["entities"]}
            for entity in context["entities"]:
                entity["parent_name"] = entity_by_id.get(entity.get("parent_id"), {}).get("name", "لا توجد — جهة رئيسية")
            context["entity_tree_nodes"] = _ordered_tree(context["entities"])
            for entity_type in context["entity_types"]:
                entity_type["entity_count"] = sum(1 for entity in context["entities"] if entity.get("entity_type_id") == entity_type.get("id"))
            context["org_units_count"] = len(context["items"])
            context["entities_count"] = len(context["entities"])
            context["entity_types_count"] = len(context["entity_types"])
            context["active_units_count"] = sum(1 for item in context["items"] if item.get("is_active"))
        elif section == "entities":
            skip = max(0, int(request.GET.get("skip", 0)))
            context["items"] = client.get("/entities", {"skip": skip, "limit": 20})
            context["entity_types"] = client.get("/entities/entity-types")
            context.update(next=skip+20, has_next=len(context["items"]) == 20)
        elif section == "users":
            skip = max(0, int(request.GET.get("skip", 0)))
            filters = {k: v for k, v in request.GET.items() if k in ("search", "organization_id", "is_active") and v}
            context["items"] = client.get("/users/", {**filters, "skip": skip, "limit": 20})
            context["total"] = client.get("/users/summary", filters)["total"]
            context["can_export_users"] = identity.get("is_admin") or "core.users.export" in identity.get("permissions", [])
            context.update(previous=max(0, skip-20), next=skip+20, has_next=skip+20 < context["total"])
            if identity.get("is_admin"):
                context["units"] = client.get("/org-units")
                context["roles"] = client.get("/roles/")
        elif section == "roles":
            context["items"] = client.get("/roles/")
            context["permissions"] = client.get("/permissions/")
            for role in context["items"]:
                role["permissions"] = client.get("/roles/" + str(role["id"]) + "/permissions")
        elif section == "settings":
            context["items"] = client.get("/settings")
            for setting in context["items"]:
                setting["display_value"] = str(setting["value"]) if setting["data_type"] == "string" else json.dumps(setting["value"], ensure_ascii=False)
            context["personal"] = client.get("/user-settings")
        elif section == "notifications":
            skip = max(0, int(request.GET.get("skip", 0)))
            context["items"] = client.get("/notifications", {"unread": request.GET.get("unread") == "1", "skip": skip, "limit": 20})
            context.update(next=skip+20, has_next=len(context["items"]) == 20)
            context["unread"] = client.get("/notifications/unread-count")["count"]
        elif section == "audit":
            params = {k: v for k, v in request.GET.items() if k in ("module", "action", "search", "date_from", "date_to", "skip", "user_id", "severity", "status_code") and v}
            result = client.get("/audit/logs", params)
            context.update(items=result["items"], total=result["total"], next=result["skip"]+result["limit"], has_next=result["skip"]+result["limit"] < result["total"])
            if request.GET.get("event"):
                context["audit_event"] = client.get("/audit/logs/" + str(int(request.GET["event"])))
                for key in ("old", "new"):
                    context["audit_event"][key] = json.dumps(context["audit_event"][key], ensure_ascii=False, indent=2)
        elif section == "profile":
            context["sessions"] = client.get("/profile/sessions")
            context["personal"] = client.get("/user-settings/effective")
            context["notification_preferences"] = client.get("/user-notification-settings/available")
    except UnauthorizedException:
        request.session.flush()
        messages.warning(request, "انتهت جلستك بسبب الخمول لمدة 10 دقائق أو إعادة تشغيل النظام؛ سجّل الدخول مجددًا")
        return redirect("auth:login")
    except ForbiddenException:
        context["error"] = "ليس لديك صلاحية الوصول إلى هذه الصفحة أو تنفيذ هذا الإجراء."
        return render(request, "core/workspace.html", context, status=403)
    except (ApiException, ValueError, KeyError) as exc:
        context["error"] = str(exc)
        return render(request, "core/workspace.html", context, status=400)
    from core.workspace_forms import decorate
    next_query = request.GET.copy()
    next_query["skip"] = context.get("next", 0)
    next_query.pop("event", None)
    context["next_query"] = next_query.urlencode()
    from core.workspace_ui import prepare
    template_name = ("core/workspace_organizations.html" if section == "units" else
                     ("core/workspace_pilot.html" if section == "home" and use_pilot(request, identity) else "core/workspace.html"))
    return render(request, template_name, prepare(decorate(context)))


def perform(request, client, section):
    data, action = request.POST, request.POST.get("action", "")
    uid = quote(data.get("id", ""), safe="")
    if section == "units" and action in ("create", "update"):
        body = {"name": data["name"], "parent_id": data.get("parent_id") or None,
                "is_active": data.get("is_active", "true") == "true"}
        (client.post("/org-units", body) if action == "create" else client.put("/org-units/" + uid, body))
    elif section in ("units", "entities") and action == "create_type":
        client.post("/entities/entity-types", {"name": data["name"], "code": data["code"]})
    elif section in ("units", "entities") and action in ("create_entity", "update_entity"):
        body = {key: data.get(key) or None for key in ("name", "code", "entity_type_id", "contact_person", "email", "phone", "address", "parent_id")}
        if action == "update_entity":
            body["is_active"] = data.get("is_active") == "true"
            client.put("/entities/" + uid, body)
        else:
            client.post("/entities", body)
    elif section == "users" and action == "create":
        body = {k: data[k] for k in ("username", "password", "full_name", "email", "organization_id")}
        body["role_names"] = [data["role"]] if data.get("role") else []
        client.post("/auth/register", body)
    elif section == "users" and action == "update":
        body = {"full_name": data["full_name"], "phone": data.get("phone"), "is_active": data.get("is_active") == "true"}
        body.update({key: data[key] for key in ("email", "organization_id") if data.get(key)})
        client.put("/users/" + uid, body)
    elif section == "users" and action == "reset_password":
        client.put("/users/" + uid + "/password", {"new_password": data["new_password"]})
    elif section == "users" and action == "assign":
        client.post("/users/" + uid + "/roles", {"role_name": data["role"], "scope": data["scope"]})
    elif section == "users" and action == "remove_role":
        client.delete("/users/" + uid + "/roles/" + str(int(data["role_id"])))
    elif section == "roles" and action == "create":
        client.post("/roles/", {"name": data["name"], "description": data.get("description", "")})
    elif section == "roles" and action == "grant":
        client.post("/roles/" + str(int(data["id"])) + "/permissions", {"permission_id": int(data["permission_id"])})
    elif section == "roles" and action == "revoke":
        client.delete("/roles/" + str(int(data["id"])) + "/permissions/" + str(int(data["permission_id"])))
    elif section == "settings" and action == "save":
        client.put("/settings/by-key/" + quote(data["key"], safe=""), {"value": data["value"] if data.get("data_type") == "string" else json.loads(data["value"])})
    elif section == "settings" and action == "reset":
        client.post("/settings/by-key/" + quote(data["key"], safe="") + "/reset")
    elif section == "settings" and action == "policy":
        client.put("/settings/by-key/" + quote(data["key"], safe=""), {"allow_user_override": data["allow_user_override"] == "true"})
    elif section == "notifications" and action == "read":
        client.put("/notifications/mark-read/" + uid)
    elif section == "notifications" and action == "read_all":
        client.put("/notifications/mark-all-read")
    elif section == "profile" and action == "profile":
        client.put("/profile", {"full_name": data["full_name"], "phone": data.get("phone")})
    elif section == "profile" and action == "password":
        client.put("/profile/password", {"current_password": data["current_password"], "new_password": data["new_password"]})
        request.session.flush()
    elif section == "profile" and action == "revoke":
        client.delete("/profile/sessions/" + uid)
    elif section == "profile" and action == "preference":
        value = int(data["value"]) if data["key"] == "font_size" else data["value"]
        client.put("/user-settings/" + quote(data["key"], safe=""), {"value": value})
    elif section == "profile" and action == "reset_preference":
        client.delete("/user-settings/" + quote(data["key"], safe=""))
    elif section == "profile" and action == "notification_preference":
        client.put("/user-notification-settings/by-type/" + quote(data["notification_type"], safe=""), {"is_enabled": data["is_enabled"] == "true"})
    else:
        raise ValueError("الإجراء غير متاح")


def audit_export(request, resource="audit"):
    import requests
    from django.conf import settings
    permitted = ("module", "action", "search", "date_from", "date_to", "user_id", "severity", "status_code") if resource == "audit" else ("search", "organization_id", "is_active")
    parameters = {k: v for k, v in request.GET.items() if k in permitted}
    try:
        ApiClient().get("/auth/me")
        response = requests.get(settings.API_BASE_URL.rstrip("/") + "/" + resource + "/export",
            params=parameters, headers={"Authorization": "Bearer " + request.session.get("access_token", "")}, timeout=30)
        if response.status_code != 200:
            return HttpResponse("تعذر التصدير أو لا توجد صلاحية", status=response.status_code)
        result = HttpResponse(response.content, content_type="text/csv; charset=utf-8")
        result["Content-Disposition"] = 'attachment; filename="' + resource + '.csv"'
        return result
    except requests.RequestException:
        return HttpResponse("تعذر الاتصال بالخادم", status=503)
    except ApiException:
        return HttpResponse("تعذر التحقق من الجلسة", status=401)
