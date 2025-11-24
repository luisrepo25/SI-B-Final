
from django.urls import path
from . import views
from . import api


urlpatterns = [
    # auth actions
    path('login/', views.login),
    path('register/', views.register),
    path('perfil/', views.perfil),
    path('logout/', views.logout),

    # compatibility/user management endpoints (English aliases)
    path('roles/', api.RolViewSet.as_view({'get': 'list'}), name='roles-list'),
    path('users/<int:pk>/roles/', api.UserRolesView.as_view(), name='user-roles'),
    path('users/<int:pk>/roles/<role_slug>/', api.UserRolesView.as_view(), name='user-role-delete'),
    path('users/', api.UsersListView.as_view(), name='users-list'),
    path('users/<int:pk>/', api.UserDetailView.as_view(), name='user-detail'),
    path('users/<int:pk>/active/', api.SetUserActiveView.as_view(), name='user-set-active'),
    path('users/me/', api.MeView.as_view(), name='user-me'),
    # compatibility Spanish path used by older frontend
    path('usuarios/<int:pk>/editar-datos/', api.UserDetailView.as_view(), name='usuario-editar-datos'),
]