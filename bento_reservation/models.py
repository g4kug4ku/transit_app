from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class BentoReservation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reservation_date = models.DateTimeField()
    main_dish = models.BooleanField(default=False)
    rice = models.BooleanField(default=False)
    rice_weight = models.IntegerField(null=True, blank=True)
    received = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.user} - {self.reservation_date}"