from django.urls import path
from . import views

app_name = 'bento_reservation'

urlpatterns = [
    path('reservation/<str:date>/', views.reservation_view, name='reservation'),
    path('reservation/success/', views.reservation_success_view, name='reservation_success'),
]