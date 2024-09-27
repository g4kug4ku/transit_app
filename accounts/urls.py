# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('post/<slug:slug>/', views.post_detail, name='post_detail'),
    path('post/<slug:slug>/like/', views.like_post, name='like_post'),
    path('bento_reservation/', views.bento_reservation, name='bento_reservation'),
    path('reservation_list/', views.reservation_list, name='reservation_list'),
    path('reservation/receive/<int:reservation_id>/', views.receive_bento, name='receive_bento'),
    path('cancel_reservation/<int:reservation_id>/', views.cancel_reservation, name='cancel_reservation'),
    path('admin_bento_reservation_list/', views.admin_bento_reservation_list, name='admin_bento_reservation_list'),
]
