from django.urls import path

from .pdf_views import AdminPDFView, StudentPDFView


def pdf_routes(prefix, view, name):
    return [
        path(f'{prefix}pdf/', view.as_view(operation='generate', http_method_names=['post', 'options']), name=f'{name}-pdf-request'),
        path(f'{prefix}pdf/status/', view.as_view(operation='status', http_method_names=['get', 'head', 'options']), name=f'{name}-pdf-status'),
        path(f'{prefix}pdf/download/', view.as_view(operation='download', http_method_names=['get', 'head', 'options']), name=f'{name}-pdf-download'),
    ]


urlpatterns = [
    *pdf_routes('student/passport/', StudentPDFView, 'student-passport'),
    *pdf_routes('student/passport/versions/<uuid:id>/', StudentPDFView, 'student-passport-version'),
    *pdf_routes('admin/passports/<uuid:id>/', AdminPDFView, 'admin-passport'),
]
