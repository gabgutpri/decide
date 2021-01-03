from django.urls import include, path
from rest_framework.authtoken.views import obtain_auth_token

from django.urls import include, path, re_path
from django.contrib.auth import views as auth_views

from .views import GetUserView, LogoutView, RegisterView, RegisterGUI, LogOutTestView, AccountActivation



urlpatterns = [
    path('login/', obtain_auth_token),
    path('logout/', LogoutView.as_view()),
    path('getuser/', GetUserView.as_view()),
    path('register/', RegisterView.as_view()),
    #Register URL
    path('registergui/', RegisterGUI.register, name='account_activation_sent'),
    #Login URL Built In
    path('logingui/', auth_views.login,{'template_name': 'login.html'}, name='login2'),<a href="{% url 'social:begin' 'twitter' %}">Acceder con Twitter</a>
    #Logout URL
    path('logoutgui/', LogOutTestView.logout, name='logout'),
    #Registration Form
    path('registergui/', RegisterGUI.register, name='account_activation_sent'),
    #Account activation sent view
    path(r'^account_activation_sent/$', AccountActivation.account_activation_sent, name='account_activation_sent'),
    #Activation URL
    path('activate/<slug:uidb64>/<slug:token>/', AccountActivation.activate, name='activate'),
]
