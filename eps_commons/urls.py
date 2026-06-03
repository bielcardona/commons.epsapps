from django.urls import path

from . import views

urlpatterns = [
    path('swap_rol/<str:group_name>', views.swap_rol, name='swap_rol'),
    path('impersonate/', views.impersonate_list, name='impersonate_list'),
    path('impersonate/<str:username>/', views.impersonate_user, name='impersonate_user'),
    path('stop-impersonation/', views.stop_impersonation, name='stop_impersonation'),
    path('oauth/login/', views.oauth_login, name='oauth_login'),
    path('oauth/callback/', views.oauth_callback, name='oauth_callback'),
    path('oauth/userinfo/', views.user_info, name='oauth_userinfo'),
    path('oauth/logout/', views.logout_view, name='oauth_logout'),
]
