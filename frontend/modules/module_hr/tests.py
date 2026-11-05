from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase
from django.utils import timezone

from shared.services.api_client import ApiException, ForbiddenException
from .views import employee_detail, home


class HRViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def request(self, method, path, data=None):
        request = getattr(self.factory, method)(path, data or {})
        request.session = {"access_token": "test-token"}
        return request

    @patch("modules.module_hr.views.ApiClient.get")
    def test_employees_screen_renders_rtl_hr_shell(self, get):
        def response(endpoint, *args, **kwargs):
            if endpoint == "/auth/me":
                return {"is_admin": True, "permissions": []}
            return []

        get.side_effect = response
        result = home(self.request("get", "/hr/?section=employees"))
        self.assertEqual(result.status_code, 200)
        self.assertIn('dir="rtl"', result.content.decode())
        self.assertIn("قائمة الموظفين", result.content.decode())

    @patch("modules.module_hr.views.ApiClient.get")
    def test_employee_detail_loads_scoped_profile_and_selected_tab(self, get):
        employee_id = "12345678-1234-5678-1234-567812345678"

        def response(endpoint, params=None, **kwargs):
            if endpoint in {"/settings-center/branding", "/modules", "/user-settings/effective"}:
                return {}
            if endpoint == "/auth/me":
                return {"is_admin": False, "permissions": ["hr.employees.view"]}
            if endpoint == f"/hr/employees/{employee_id}":
                return {"id": employee_id, "full_name": "موظف نطاق", "employee_no": "HR-001",
                        "employment_status": "active", "position_title": "أخصائي"}
            if endpoint == f"/hr/employees/{employee_id}/employment-records":
                self.assertEqual(params, {})
                return {"items": [{"change_type": "appointment", "status": "approved"}]}
            raise AssertionError(f"Unexpected API endpoint: {endpoint}")

        get.side_effect = response
        result = employee_detail(self.request("get", f"/hr/employees/{employee_id}/?tab=history"), employee_id)

        self.assertEqual(result.status_code, 200)
        content = result.content.decode()
        self.assertIn("التبعية الإدارية والتاريخ الوظيفي", content)
        self.assertIn("موظف نطاق", content)
        self.assertIn("hr-detail-tabs", content)

    @patch("modules.module_hr.views.ApiClient.get")
    def test_employee_detail_hides_out_of_scope_profile(self, get):
        get.side_effect = [
            {"is_admin": False, "permissions": ["hr.employees.view"]},
            ForbiddenException("not permitted"),
        ]
        result = employee_detail(
            self.request("get", "/hr/employees/12345678-1234-5678-1234-567812345678/"),
            "12345678-1234-5678-1234-567812345678",
        )

        self.assertEqual(result.status_code, 404)

    @patch("modules.module_hr.views.ApiClient.get")
    def test_employees_screen_accepts_compact_api_uuid_links(self, get):
        compact_id = "12345678123456781234567812345678"

        def response(endpoint, params=None, **kwargs):
            if endpoint in {"/settings-center/branding", "/modules", "/user-settings/effective"}:
                return {}
            if endpoint == "/auth/me":
                return {"is_admin": True, "permissions": []}
            if endpoint == "/hr/employees":
                return {"items": [{"id": compact_id, "full_name": "موظف اختبار", "employee_no": "HR-UUID-1",
                                    "employment_status": "active"}], "total": 1, "page": 1, "page_size": 20}
            return []

        get.side_effect = response
        result = home(self.request("get", "/hr/?section=employees"))
        self.assertEqual(result.status_code, 200)
        self.assertIn("/hr/employees/12345678-1234-5678-1234-567812345678/", result.content.decode())

    @patch("modules.module_hr.views.ApiClient.get")
    def test_decisions_screen_renders_real_status_and_future_badges(self, get):
        def response(endpoint, params=None, **kwargs):
            if endpoint in {"/settings-center/branding", "/modules", "/user-settings/effective"}:
                return {}
            if endpoint == "/auth/me":
                return {"is_admin": False, "permissions": ["hr.employment_records.view"]}
            if endpoint == "/hr/employment-records":
                return {"items": [{
                    "id": "decision-1", "reference_no": "HR-2026-001", "employee_no": "HR-001",
                    "full_name": "موظف قرار", "change_type": "transfer", "status": "approved",
                    "effective_date": "2999-01-01", "created_at": "2026-01-01T00:00:00",
                    "home_unit_name": "إدارة الاختبار",
                }], "total": 1, "page": 1, "pages": 1, "page_size": 10,
                        "summary": {"total": 1, "approved": 1, "future": 1, "review": 0}, "units": []}
            raise AssertionError(f"Unexpected API endpoint: {endpoint}")

        get.side_effect = response
        result = home(self.request("get", "/hr/?section=decisions"))
        content = result.content.decode()

        self.assertEqual(result.status_code, 200)
        self.assertIn("القرارات الإدارية", content)
        self.assertIn("HR-2026-001", content)
        self.assertIn("future", content)
        self.assertIn("عرض القرار", content)

    @patch("modules.module_hr.views.ApiClient.post")
    @patch("modules.module_hr.views.ApiClient.get")
    def test_employee_create_proxies_to_scoped_backend(self, get, post):
        get.return_value = {"is_admin": True, "permissions": []}
        result = home(self.request("post", "/hr/?section=employees", {
            "action": "employee_create",
            "employee_no": "HR-UI-1",
            "full_name": "موظف اختبار",
            "home_unit_id": "12345678123456781234567812345678",
        }))
        self.assertEqual(result.status_code, 302)
        post.assert_called_once_with("/hr/employees", {
            "employee_no": "HR-UI-1",
            "full_name": "موظف اختبار",
            "home_unit_id": "12345678123456781234567812345678",
        })

    @patch("modules.module_hr.views.ApiClient.get")
    def test_screen_permission_is_enforced(self, get):
        get.return_value = {"is_admin": False, "permissions": ["hr.employees.view"]}
        result = home(self.request("get", "/hr/?section=workforce"))
        self.assertEqual(result.status_code, 403)

    @patch("modules.module_hr.views.ApiClient.get")
    def test_dashboard_uses_scoped_api_data_without_sample_values(self, get):
        today = timezone.localdate().isoformat()

        def response(endpoint, params=None, **kwargs):
            if endpoint == "/settings-center/branding":
                return {}
            if endpoint == "/modules":
                return []
            if endpoint == "/user-settings/effective":
                return []
            if endpoint == "/auth/me":
                return {"is_admin": True, "permissions": []}
            if endpoint == "/hr/employees":
                return {"items": [
                    {"full_name": "Restricted Employee", "employment_status": "active"},
                    {"full_name": "Another Employee", "employment_status": "inactive"},
                ]}
            if endpoint == "/hr/shift-roster":
                return {"items": [
                    {"id": "shift-1", "business_date": today, "status": "confirmed"},
                    {"id": "shift-2", "business_date": today, "status": "confirmed"},
                    {"id": "shift-3", "business_date": today, "status": "draft"},
                ]}
            if endpoint == "/hr/attendance":
                self.assertEqual(params, {"business_date": today})
                return {"items": [{
                    "shift_roster_id": "shift-1",
                    "attendance_kind": "base_shift",
                    "is_current": True,
                    "status": "absent",
                }]}
            if endpoint == "/hr/field-tasks":
                return {"items": [{"status": "in_progress"}]}
            if endpoint == "/hr/workforce-requests":
                return {"items": [{"status": "submitted"}]}
            if endpoint == "/hr/issues":
                return {"items": [{"solution_status": "not_started"}]}
            return {"items": []}

        get.side_effect = response
        result = home(self.request("get", "/hr/"))
        content = result.content.decode()

        self.assertEqual(result.status_code, 200)
        self.assertIn("إجمالي الموظفين", content)
        self.assertIn("الموظفون والقرارات", content)
        self.assertIn("المهام والتوزيع", content)
        self.assertIn("الورديات والحضور", content)
        self.assertIn("المشكلات التشغيلية", content)
        self.assertIn("التقارير والمؤشرات", content)
        self.assertIn("50%", content)
        self.assertIn("تسجيل حضور اليوم", content)
        self.assertIn("?section=employees", content)
        self.assertIn("?section=workforce", content)
        self.assertIn("?section=shifts", content)
        self.assertIn("?section=issues", content)
        self.assertNotIn("324", content)
        self.assertNotIn("Restricted Employee", content)
        self.assertNotIn("غياب مؤكد", content)

    @patch("modules.module_hr.views.ApiClient.get")
    def test_report_permission_can_open_the_existing_reports_area(self, get):
        def response(endpoint, *args, **kwargs):
            if endpoint == "/settings-center/branding":
                return {}
            if endpoint == "/modules":
                return []
            if endpoint == "/user-settings/effective":
                return []
            if endpoint == "/auth/me":
                return {"is_admin": False, "permissions": ["hr.report.view"]}
            if endpoint == "/hr/issues":
                raise ForbiddenException("not permitted")
            if endpoint.startswith("/hr/reports/"):
                return {"items": []}
            raise AssertionError(f"Unexpected API endpoint: {endpoint}")

        get.side_effect = response
        result = home(self.request("get", "/hr/?section=issues"))
        content = result.content.decode()

        self.assertEqual(result.status_code, 200)
        self.assertIn("تقرير الحضور", content)
        self.assertIn("تقرير المشكلات", content)

    @patch("modules.module_hr.views.ApiClient.get")
    def test_admin_can_render_issue_and_report_forms(self, get):
        def response(endpoint, *args, **kwargs):
            if endpoint == "/settings-center/branding":
                return {}
            if endpoint == "/modules":
                return []
            if endpoint == "/user-settings/effective":
                return []
            if endpoint == "/auth/me":
                return {"is_admin": True, "permissions": []}
            if endpoint == "/hr/issues":
                return {"items": []}
            if endpoint.startswith("/hr/reports/"):
                return {"items": []}
            raise AssertionError(f"Unexpected API endpoint: {endpoint}")

        get.side_effect = response
        result = home(self.request("get", "/hr/?section=issues"))

        self.assertEqual(result.status_code, 200)
        self.assertIn("تقرير الحضور", result.content.decode())
        self.assertIn("تصدير تقرير CSV", result.content.decode())

    @patch("modules.module_hr.views.ApiClient.get")
    def test_dashboard_disables_cards_outside_user_permissions(self, get):
        def response(endpoint, *args, **kwargs):
            if endpoint == "/settings-center/branding":
                return {}
            if endpoint == "/modules":
                return []
            if endpoint == "/user-settings/effective":
                return []
            if endpoint == "/auth/me":
                return {"is_admin": False, "permissions": ["hr.report.view"]}
            raise AssertionError(f"Unexpected API endpoint: {endpoint}")

        get.side_effect = response
        result = home(self.request("get", "/hr/?section=dashboard"))
        content = result.content.decode()

        self.assertEqual(result.status_code, 200)
        self.assertIn('class="hr-home-card blue is-disabled" aria-disabled="true"', content)
        self.assertIn('class="hr-home-card cyan"', content)
        self.assertIn("لا تتوفر صلاحية عرض البيانات", content)
        self.assertIn('href="/hr/?section=issues"', content)

    @patch("modules.module_hr.views.ApiClient.get")
    def test_dashboard_surfaces_api_failure_without_zero_fallback(self, get):
        def response(endpoint, *args, **kwargs):
            if endpoint == "/settings-center/branding":
                return {}
            if endpoint == "/modules":
                return []
            if endpoint == "/user-settings/effective":
                return []
            if endpoint == "/auth/me":
                return {"is_admin": True, "permissions": []}
            raise ApiException("service unavailable")

        get.side_effect = response
        result = home(self.request("get", "/hr/?section=dashboard"))
        content = result.content.decode()

        self.assertEqual(result.status_code, 200)
        self.assertIn("تعذّر تحميل بعض المؤشرات", content)
        self.assertIn("تعذر تحميل البيانات", content)
        self.assertNotIn("324", content)
