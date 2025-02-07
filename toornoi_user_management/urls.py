from django.urls import path
from .views import  RegisterUserView, SuperAdminLoginView, SuperAdminProfileView, SuperAdminUpdateProfileView, UserLoginView, UserProfileView, UserUpdateProfileView, VerifyEmailView
urlpatterns = [
    path('superadmin/login/', SuperAdminLoginView.as_view(), name='superadmin-login'),
    path('superadmin/profile/', SuperAdminProfileView.as_view(), name='superadmin-profile'),  # Fetch profile
    path('superadmin/profile/update/', SuperAdminUpdateProfileView.as_view(), name='superadmin-update-profile'),  # Update profile
     #Register user
    path('register/', RegisterUserView.as_view(), name='register'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('login/', UserLoginView.as_view(), name='user-login'),
    path('user/profile/', UserProfileView.as_view(), name='user-profile'),  # Fetch profile
    path('user/profile/update/', UserUpdateProfileView.as_view(), name='user-update-profile'), 
]