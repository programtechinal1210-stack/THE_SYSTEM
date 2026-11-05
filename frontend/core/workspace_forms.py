"""Declarative server-rendered forms for the shared Core workspace."""


def field(name, label, value="", options=None, kind="text", required=True):
    return dict(name=name, label=label, value=value, options=options, type=kind, required=required)


def options(items, value="id", label="name"):
    return [dict(value=str(item[value]), label=item[label]) for item in items]


def form(title, action, fields):
    return dict(title=title, action=action, fields=fields)


def entity_parent_options(items, current_id=None):
    descendants = set()
    children = {}
    for item in items:
        children.setdefault(item.get("parent_id"), []).append(item["id"])
    pending = list(children.get(current_id, []))
    while pending:
        identifier = pending.pop()
        if identifier in descendants:
            continue
        descendants.add(identifier)
        pending.extend(children.get(identifier, []))
    allowed = [item for item in items if item.get("is_active") and item["id"] != current_id and item["id"] not in descendants]
    return [dict(value="", label="لا توجد — جهة رئيسية")] + options(allowed)


def decorate(context):
    section, items = context["section"], context.get("items", [])
    forms = context["forms"] = []
    context["rows"] = []
    admin = context.get("identity", {}).get("is_admin")
    if section == "units":
        context["headings"] = ["الوحدة", "تتبع", "الحالة"]
        context["rows"] = [[i["name"], i["parent_name"], "نشطة" if i["is_active"] else "معطلة"] for i in items]
        if context.get("can_manage"):
            parents = [dict(value="", label="وحدة رئيسية")] + options(items)
            forms.append(form("إضافة وحدة تنظيمية", "create", [field("name", "اسم الوحدة"), field("parent_id", "الوحدة الأعلى", options=parents, required=False)]))
            for item in items:
                forms.append(form("تعديل / نقل: " + item["name"], "update", [
                    field("id", "الوحدة", options=options([item])), field("name", "الاسم", item["name"]),
                    field("parent_id", "الوحدة الأعلى", item.get("parent_id") or "", parents, required=False),
                    field("is_active", "الحالة", "true" if item["is_active"] else "false", [dict(value="true", label="نشطة"), dict(value="false", label="معطلة")])]))
            types = context.get("entity_types", [])
            entities = context.get("entities", [])
            forms.append(form("إضافة نوع جهة", "create_type", [field("name", "اسم النوع"), field("code", "رمز النوع")]))
            def entity_fields(item, current_id=None):
                return [field("name", "اسم الجهة", item.get("name", "")), field("code", "الرمز", item.get("code") or "", required=False),
                    field("entity_type_id", "نوع الجهة", item.get("entity_type_id", ""), options(types)),
                    field("parent_id", "الجهة الأم", item.get("parent_id") or "", entity_parent_options(entities, current_id), required=False),
                    field("contact_person", "مسؤول التواصل", item.get("contact_person") or "", required=False),
                    field("email", "البريد الإلكتروني", item.get("email") or "", kind="email", required=False),
                    field("phone", "الهاتف", item.get("phone") or "", required=False),
                    field("address", "العنوان", item.get("address") or "", required=False)]
            if types:
                forms.append(form("جهة جديدة", "create_entity", entity_fields({})))
                for item in entities:
                    forms.append(form("تعديل: " + item["name"], "update_entity", [field("id", "الجهة", options=options([item]))] + entity_fields(item, item["id"]) + [field("is_active", "الحالة", "true" if item["is_active"] else "false", [dict(value="true", label="نشطة"), dict(value="false", label="معطلة")])]))
    elif section == "entities":
        types = context.get("entity_types", [])
        type_names = {item["id"]: item["name"] for item in types}
        context["headings"] = ["الجهة", "النوع", "مسؤول التواصل", "الهاتف", "الحالة"]
        context["rows"] = [[item["name"], type_names.get(item["entity_type_id"], "—"), item.get("contact_person"), item.get("phone"), "نشطة" if item["is_active"] else "معطلة"] for item in items]
        if context.get("can_manage"):
            forms.append(form("إضافة نوع جهة", "create_type", [field("name", "اسم النوع"), field("code", "رمز النوع")]))
            def entity_fields(item):
                return [field("name", "اسم الجهة", item.get("name", "")), field("code", "الرمز", item.get("code") or "", required=False),
                    field("entity_type_id", "نوع الجهة", item.get("entity_type_id", ""), options(types)),
                    field("contact_person", "مسؤول التواصل", item.get("contact_person") or "", required=False),
                    field("email", "البريد الإلكتروني", item.get("email") or "", kind="email", required=False),
                    field("phone", "الهاتف", item.get("phone") or "", required=False)]
            if types:
                forms.append(form("جهة جديدة", "create", entity_fields({})))
                for item in items:
                    forms.append(form("تعديل: " + item["name"], "update", [field("id", "الجهة", options=options([item]))] + entity_fields(item) + [field("is_active", "الحالة", "true" if item["is_active"] else "false", [dict(value="true", label="نشطة"), dict(value="false", label="معطلة")])]))
    elif section == "users":
        context["headings"] = ["الاسم", "اسم المستخدم", "البريد", "الأدوار", "الحالة"]
        context["rows"] = [[i["full_name"], i["username"], i["email"], "، ".join(i["roles"]), "نشط" if i["is_active"] else "معطل"] for i in items]
        if admin:
            forms.append(form("مستخدم جديد", "create", [field("full_name", "الاسم الكامل"), field("username", "اسم المستخدم"), field("email", "البريد الإلكتروني", kind="email"), field("password", "كلمة المرور الأولية", kind="password"), field("organization_id", "الوحدة التنظيمية", options=options(context["units"])), field("role", "الدور", options=[dict(value="", label="دون دور")] + options(context["roles"], "name"), required=False)]))
            forms.append(form("إسناد دور ونطاق بيانات", "assign", [field("id", "المستخدم", options=options(items, label="full_name")), field("role", "الدور", options=options(context["roles"], "name")), field("scope", "النطاق", options=[dict(value="self", label="بيانات المستخدم"), dict(value="organization", label="إدارته"), dict(value="institution", label="المؤسسة")])]))
            forms.append(form("إزالة إسناد دور", "remove_role", [field("id", "المستخدم", options=options(items, label="full_name")), field("role_id", "الدور", options=options(context["roles"]))]))
        if admin:
            forms.append(form("إعادة تعيين كلمة المرور", "reset_password", [field("id", "المستخدم", options=options(items, label="full_name")), field("new_password", "كلمة المرور الجديدة", kind="password")]))
        if context.get("can_manage"):
            for item in items:
                forms.append(form("تعديل: " + item["full_name"], "update", [field("id", "المستخدم", options=options([item], label="full_name")), field("full_name", "الاسم", item["full_name"]), field("phone", "الهاتف", item.get("phone") or "", required=False), field("is_active", "الحالة", "true" if item["is_active"] else "false", [dict(value="true", label="نشط"), dict(value="false", label="معطل")])]))
                forms[-1]["fields"].append(field("email", "البريد الإلكتروني", item["email"], kind="email"))
                if admin:
                    forms[-1]["fields"].append(field("organization_id", "نقل العضوية إلى وحدة", item["organization_id"], options(context["units"])))
    elif section == "roles":
        context["headings"] = ["الدور", "الوصف", "الصلاحيات"]
        context["rows"] = [[i["name"], i.get("description"), "، ".join(p["code"] for p in i["permissions"])] for i in items]
        if admin:
            forms.append(form("دور جديد", "create", [field("name", "الاسم"), field("description", "الوصف", required=False)]))
            for action, label in [("grant", "إضافة صلاحية"), ("revoke", "إزالة صلاحية")]:
                forms.append(form(label, action, [field("id", "الدور", options=options(items)), field("permission_id", "الصلاحية", options=options(context["permissions"], label="code"))]))
    elif section == "settings":
        context["headings"] = ["الإعداد", "القيمة", "النوع"]
        context["rows"] = [[i.get("description_ar") or i["key"], i["display_value"], i["data_type"]] for i in items]
        if context.get("can_manage"):
            for item in items:
                forms.append(form("تعديل: " + (item.get("description_ar") or item["key"]), "save", [field("key", "الإعداد", options=[dict(value=item["key"], label=item["key"])]), field("value", "القيمة", item["display_value"]), field("data_type", "نوع القيمة", options=[dict(value=item["data_type"], label=item["data_type"])])]))
            forms.append(form("استعادة قيمة افتراضية", "reset", [field("key", "الإعداد", options=options(items, "key", "key"))]))
            personal_definitions = [i for i in items if i["key"] in ("core.theme", "core.font_size", "core.language")]
            if personal_definitions:
                forms.append(form("سياسة تخصيص المستخدم", "policy", [field("key", "الإعداد", options=options(personal_definitions, "key", "key")), field("allow_user_override", "السماح بالتخصيص", options=[dict(value="false", label="مقفل على قيمة النظام"), dict(value="true", label="السماح بتفضيل المستخدم")])]))
    elif section == "notifications":
        context["headings"] = ["الإشعار", "التفاصيل", "الوقت", "الحالة"]
        context["rows"] = [[i["title"], i["content"], i["created_at"], "مقروء" if i["is_read"] else "جديد"] for i in items]
    elif section == "audit":
        context["audit_actions"] = ["CREATE", "UPDATE", "DELETE", "LOGIN", "LOGOUT", "REFRESH", "EXPORT", "REQUEST_DENIED"]
        context["headings"] = ["الوقت", "العملية", "الوحدة", "الوصف"]
        context["rows"] = [[i["created_at"], i["action"], i["module"], i["changes_summary"]] for i in items]
    elif section == "profile":
        user = context["identity"]
        context["headings"] = ["التفضيل", "القيمة الفعالة", "المصدر", "القفل"]
        context["rows"] = [[item["setting_key"], item["value"], {"user": "المستخدم", "system": "النظام", "default": "الافتراضي"}.get(item["source"], item["source"]), "مقفل" if item["locked"] else "قابل للتعديل"] for item in context.get("personal", [])]
        forms.append(form("البيانات الشخصية", "profile", [field("full_name", "الاسم", user["full_name"]), field("phone", "الهاتف", user.get("phone") or "", required=False)]))
        forms.append(form("تغيير كلمة المرور وإنهاء الجلسات", "password", [field("current_password", "الحالية", kind="password"), field("new_password", "الجديدة", kind="password")]))
        forms.append(form("مظهر الواجهة", "preference", [field("key", "الإعداد", options=[dict(value="theme", label="المظهر")]), field("value", "المظهر", options=[dict(value="light", label="فاتح"), dict(value="dark", label="داكن")])]))
        forms.append(form("حجم الخط", "preference", [field("key", "الإعداد", options=[dict(value="font_size", label="حجم الخط")]), field("value", "الحجم من 12 إلى 24", kind="number")]))
        forms.append(form("استخدام إعدادات النظام", "reset_preference", [field("key", "التفضيل", options=[dict(value="theme", label="المظهر"), dict(value="font_size", label="حجم الخط")])]))
        for item in context.get("notification_preferences", []):
            forms.append(form("إشعارات: " + item["notification_type"], "notification_preference", [
                field("notification_type", "النوع", options=[dict(value=item["notification_type"], label=item["notification_type"])]),
                field("is_enabled", "الإشعارات الداخلية", "true" if item["is_enabled"] else "false", [dict(value="true", label="مفعلة"), dict(value="false", label="متوقفة")])]))
    return context
