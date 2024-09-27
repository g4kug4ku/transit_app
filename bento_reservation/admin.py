from django.contrib import admin
from .models import BentoReservation

# Register your models here.
@admin.register(BentoReservation)
class BentoReservationAdmin(admin.ModelAdmin):
    list_display = ('user', 'reservation_date', 'main_dish', 'rice', 'rice_weight', 'received')
    list_filter = ('reservation_date', 'received')
    search_fields = ('user__username', 'reservation_date')