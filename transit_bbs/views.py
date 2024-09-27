from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth import login, authenticate, logout
from .models import Post, PostView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import reverse


# Create your views here.
def frontpage(request):
    return render(request, 'transit_bbs/frontpage.html')

def signup(request):
    if request.method == 'POST':
        first_name = request.POST['first_name']
        last_name = request.POST['last_name']
        username = request.POST['username']
        password = request.POST['password']
        
        user = User.objects.create_user(username=username, password=password, first_name=first_name, last_name=last_name)
        user.save()
        
        login(request, user)
        return redirect('toppage')
    
    return render(request, 'transit_bbs/signup.html')

@login_required
def toppage(request):
    if not request.user.is_authenticated:
        return render(request, 'transit_bbs/toppage.html')
    
    posts = Post.objects.all()
    return render(request, 'transit_bbs/toppage.html', {'posts': posts})

@login_required
def post_detail(request, id):
    post = get_object_or_404(Post, id=id)
    return render(request, 'transit_bbs/post_detail.html', {'post': post})

@login_required
def toggle_interest(request, id):
    post = get_object_or_404(Post, id=id)
    if request.user in post.interested_users.all():
        post.interested_users.remove(request.user)
        interested = False
    else:
        post.interested_users.add(request.user)
        interested = True
    return JsonResponse({'interested': interested})

@login_required
def add_interest(request, id):
    post = get_object_or_404(Post, id=id)
    if request.user in post.interested_users.all():
        post.interested_users.remove(request.user)
    else:
        post.interested_users.add(request.user)
    return redirect('post_detail', id=post.id)

@login_required
def remove_interest(request, id):
    post = get_object_or_404(Post, id=id)
    interest = PostInterest.objects.filter(user=request.user, post=post).first()
    if interest:
        interest.delete()
    return redirect('post_detail', id=post.id)

@login_required
def custom_logout(request):
    logout(request)
    messages.info(request, "ログアウトしました。")
    return redirect('frontpage')