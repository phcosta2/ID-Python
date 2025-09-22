from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login as auth_login
from django.contrib import messages

@login_required
def home(request):
    return render(request, 'home.html')

def signup(request):
    if request.method == 'POST':
        username = request.POST.get('username','').strip()
        password = request.POST.get('password','')
        if not username or not password:
            messages.error(request, 'Preencha usuário e senha.')
            return redirect('signup')
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Usuário já existe.')
            return redirect('signup')
        user = User.objects.create_user(username=username, password=password)
        user = authenticate(request, username=username, password=password)
        if user:
            auth_login(request, user)
            return redirect('home')
    return render(request, 'signup.html')