from django.shortcuts import render

class Home:
    def home(request):

        context = {}
        context['profileUrl'] = "/authentication/profile/" + request.user.username

        if request.user.is_authenticated:
            return render(request, 'home_auth.html', context)
        else:
            return render(request, 'home.html')