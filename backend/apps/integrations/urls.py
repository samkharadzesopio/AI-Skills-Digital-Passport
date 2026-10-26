
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


from .views import ClassroomSyncHistoryView, ClassroomSyncRetryView

urlpatterns += [
    path('classroom/events/', ClassroomSyncHistoryView.as_view(), name='classroom-sync-history'),
    path('classroom/events/<uuid:event_id>/retry/', ClassroomSyncRetryView.as_view(), name='classroom-sync-retry'),
]

from .views import ImportHistoryView, ImportRetryView
urlpatterns += [
    path('imports/', ImportHistoryView.as_view(), name='completion-import-history'),
    path('imports/events/<uuid:event_id>/retry/', ImportRetryView.as_view(), name='completion-import-retry'),
]

from .recommendations.api import CourseRecommendationsView
urlpatterns += [
    path('course-recommendations/', CourseRecommendationsView.as_view(), name='course-recommendations'),
]
