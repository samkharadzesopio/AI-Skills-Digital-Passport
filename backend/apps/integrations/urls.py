
from django.urls import path
from .views import ClassroomCompletionsView
from .views import ClassroomSyncView

urlpatterns = [
    path(
        "classroom/completions/",
        ClassroomCompletionsView.as_view(),
        name="classroom-completions"
    ),
]

urlpatterns += [
    path(
        "classroom/sync/",
        ClassroomSyncView.as_view(),
        name="classroom-sync",
    ),
]

from .views import (
    AdminExcelImportView,
    AdminGoogleSheetsImportView,
)

urlpatterns += [
    path(
        "import/excel/",
        AdminExcelImportView.as_view(),
        name="admin-excel-import",
    ),
    path(
        "import/google-sheets/",
        AdminGoogleSheetsImportView.as_view(),
        name="admin-google-sheets-import",
    ),
]
