from django.urls import path
from .views import frontpage, signup, toppage, post_detail, custom_logout, add_interest, remove_interest

urlpatterns = [
    path('', frontpage, name='frontpage'),
    path('signup/', signup, name='signup'),
    path('toppage/', toppage, name='toppage'),
    path('post/<int:id>/', post_detail, name='post_detail'),
    path('post/<int:id>/add_interest/', add_interest, name='add_interest'),
    path('post/<int:id>/remove_interest/', remove_interest, name='remove_interest'),
    path('logout/', custom_logout, name='logout'),
]
