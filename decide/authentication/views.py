from rest_framework.response import Response
from rest_framework.status import (
        HTTP_201_CREATED,
        HTTP_400_BAD_REQUEST,
        HTTP_401_UNAUTHORIZED
)
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.core.exceptions import ObjectDoesNotExist

from .serializers import UserSerializer

from django.shortcuts import render, redirect
from django.utils.encoding import force_text, force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.sites.shortcuts import get_current_site
from django.utils.http import urlsafe_base64_decode
from django.template.loader import render_to_string
from django.http import HttpResponse

from .forms import RegisterForm
from django.contrib.auth import logout, login, authenticate

from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
 
from .tokens import account_activation_token
 
from .models import Profile


class GetUserView(APIView):
    def post(self, request):
        key = request.data.get('token', '')
        tk = get_object_or_404(Token, key=key)
        return Response(UserSerializer(tk.user, many=False).data)


class LogoutView(APIView):
    def post(self, request):
        key = request.data.get('token', '')
        try:
            tk = Token.objects.get(key=key)
            tk.delete()
        except ObjectDoesNotExist:
            pass

        return Response({})


class RegisterView(APIView):
    def post(self, request):
        key = request.data.get('token', '')
        tk = get_object_or_404(Token, key=key)
        if not tk.user.is_superuser:
            return Response({}, status=HTTP_401_UNAUTHORIZED)

        username = request.data.get('username', '')
        pwd = request.data.get('password', '')
        if not username or not pwd:
            return Response({}, status=HTTP_400_BAD_REQUEST)

        try:
            user = User(username=username)
            user.set_password(pwd)
            user.save()
            token, _ = Token.objects.get_or_create(user=user)
        except IntegrityError:
            return Response({}, status=HTTP_400_BAD_REQUEST)
        return Response({'user_pk': user.pk, 'token': token.key}, HTTP_201_CREATED)


#Sign Up View
class RegisterGUI:
    def register(request):
        if request.user.is_authenticated:
            return redirect('/')
        if request.method == 'POST':
            form = RegisterForm(request.POST)
            if form.is_valid():
                #Setting the additional fields on the BBDD
                user = form.save()
                user.refresh_from_db()
                user.profile.email = form.cleaned_data.get('email')
                user.profile.first_name = form.cleaned_data.get('first_name')
                user.profile.last_name = form.cleaned_data.get('last_name')
                user.is_active = False
                user.save()
                #Email verification handler
                current_site = get_current_site(request)
                subject = 'Your Decide account needs activation'
                message = render_to_string('account_activation_email.html', {
                    'user': user,
                    'domain': current_site.domain,
                    'uid': urlsafe_base64_encode(force_bytes(user.pk)).decode(),
                    'token': account_activation_token.make_token(user),
                })
                user.email_user(subject, message)

                return redirect('account_activation_sent')
            else:
                return render(request, 'register.html', {'form': form})
        else:
            form = RegisterForm()
            return render(request, 'register.html', {'form': form})

#Simple logout, could be improved

class LogOutTestView:
    def logout(request):
        logout(request)
        return redirect('/')

#Activation View
class AccountActivation:
    #Activation method
    def activate(request, uidb64, token):
        try:
            #Extracting the token
            uid = force_text(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        #Token verification and account activation
        if user is not None and account_activation_token.check_token(user, token):
            user.is_active = True
            user.profile.email_confirmed = True
            user.save()
            login(request, user)
            return HttpResponse('Thank you for verifying your email, you can login your account now')
        else:
            return render(request, 'account_activation_invalid.html')
 
    #Account activation sent view
    def account_activation_sent(request):
        return render(request, 'account_activation_sent.html')