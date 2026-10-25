
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIRequestFactory

from .views import (
    AdminExcelImportView,
    AdminGoogleSheetsImportView,
)


class AdminImportSecurityTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()

    def test_anonymous_excel_import_denied(self):
        request = self.factory.post(
            "/api/integrations/import/excel/",
            {},
        )

        response = AdminExcelImportView.as_view()(request)

        self.assertIn(
            response.status_code,
            [401, 403],
        )

    def test_anonymous_google_sheets_import_denied(self):
        request = self.factory.post(
            "/api/integrations/import/google-sheets/",
            {},
            format="json",
        )

        response = AdminGoogleSheetsImportView.as_view()(
            request
        )

        self.assertIn(
            response.status_code,
            [401, 403],
        )


class GoogleSheetsConfigurationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from apps.accounts.models import User

        cls.admin = User.objects.create_admin_user(
            email="sheets.admin@btu.edu.ge",
            password="Test-Admin-Password-2026!",
            permission_codenames={"import_completions"},
        )

    def admin_request(self):
        from rest_framework.test import force_authenticate

        request = APIRequestFactory().post('/', {}, format='json')
        force_authenticate(request, user=self.admin)
        return request

    def test_missing_sheet_configuration_returns_503(self):
        from django.test import override_settings
        with override_settings(BTU_GOOGLE_SHEET_ID=None):
            response = AdminGoogleSheetsImportView.as_view()(self.admin_request())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data['error'], 'Google Sheets is not configured')

    def test_configured_sheet_uses_server_selected_id(self):
        from django.test import override_settings
        from unittest.mock import patch
        with override_settings(BTU_GOOGLE_SHEET_ID='trusted-sheet-id'), patch(
            'apps.integrations.views.read_google_sheet', return_value=([], []),
        ) as read, patch(
            'apps.integrations.views.process_completion_import', return_value={'processed': 0},
        ) as process:
            response = AdminGoogleSheetsImportView.as_view()(self.admin_request())
        self.assertEqual(response.status_code, 200)
        read.assert_called_once_with(spreadsheet_id='trusted-sheet-id')
        process.assert_called_once_with([], source='BTU_GOOGLE_SHEETS')
