
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from .views import (
    AdminExcelImportView,
    AdminGoogleSheetsImportView,
)


class AdminImportSecurityTests(SimpleTestCase):

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
