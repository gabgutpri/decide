from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token

from django.urls import include, path
from django.contrib.auth import views as auth_views

from .views import GetUserView, LogoutView, RegisterView, RegisterGUI, LogOutTestView



urlpatterns = [
    path('login/', obtain_auth_token),
    path('logout/', LogoutView.as_view()),
    path('getuser/', GetUserView.as_view()),
    path('register/', RegisterView.as_view()),
    #Register URL
    path('registergui/', RegisterGUI.register, name='account_activation_sent'),
    #Login URL Built In
    path('logingui/', auth_views.login,{'template_name': 'login.html'}, name='login2'),
    #Logout URL
    path('logoutgui/', LogOutTestView.logout, name='logout'),
    #OAuth Social Login URL
    path('oauth/', include('social_django.urls', namespace='social')),
]
