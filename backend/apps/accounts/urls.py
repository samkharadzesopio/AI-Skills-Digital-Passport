from django.urls import path
from . import views

urlpatterns = [
    path('csrf/', views.csrf_token),
    path('otp/request/', views.RequestLoginCode.as_view()),
    path('otp/verify/', views.VerifyLoginCode.as_view()),
    path('logout/', views.Logout.as_view()),
]
