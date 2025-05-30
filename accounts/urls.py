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
    path('export_bento_reservations/', views.export_bento_reservations, name='export_bento_reservations'),
    path('generate_order_sheet/', views.generate_order_sheet, name='generate_order_sheet'),
    path('upload_menu/', views.upload_menu, name='upload_menu'),
    path('delete_menu/<int:menu_id>/', views.delete_menu, name='delete_menu'),
    path('kakeibo/', views.kakeibo_list, name='kakeibo_list'),
    path('kakeibo/<int:pk>/', views.kakeibo_detail, name='kakeibo_detail'),
    path('kakeibo/create/', views.kakeibo_create, name='kakeibo_create'),
    path('kakeibo/delete/<int:pk>/', views.kakeibo_delete, name='kakeibo_delete'),
    path('song_requests/', views.song_request_list, name='song_request_list'),
    path('song_requests/create/', views.song_request_create, name='song_request_create'),
    path('song_request/<int:request_id>/like/', views.toggle_like, name='toggle_like'),
    path('song_request/<int:request_id>/delete/', views.delete_song_request, name='delete_song_request'),
    path("song_requests/delete_all/", views.delete_all_song_requests, name="delete_all_song_requests"),
    path('favorite_movies/', views.favorite_movies_list, name='favorite_movies_list'),
    path('favorite_movies/new/', views.favorite_movies_create, name='favorite_movies_create'),
    path('favorite_movies/<int:pk>/', views.favorite_movies_detail, name='favorite_movies_detail'),
    path('favorite_movies/<int:pk>/delete/', views.favorite_movies_delete, name='favorite_movies_delete'),
    path("bbs/", views.bbs_top, name="bbs_top"),
    path("bbs/new/", views.new_bbs_post, name="new_bbs_post"),
    path("bbs/<int:pk>/", views.bbs_detail, name="bbs_detail"),
    path("bbs/<int:pk>/delete/", views.delete_bbs_post, name="delete_bbs_post"),
    path("bbs/<int:pk>/comment/", views.add_bbs_comment, name="add_bbs_comment"),
    path('bbs/reply/<int:pk>/', views.bbs_reply, name='bbs_reply'),
]
