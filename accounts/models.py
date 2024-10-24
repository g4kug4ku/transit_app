from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify
from datetime import timedelta, datetime, time

User = get_user_model()

# Create your models here.
class Post(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    content = models.TextField()
    attached_file = models.FileField(upload_to='attachments/', blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    read_by = models.ManyToManyField(User, related_name='read_posts', blank=True)  # 既読ユーザーのフィールド
    likes = models.ManyToManyField(User, related_name='liked_posts', blank=True)
    new_comment = models.BooleanField(default=False)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return self.title
    
    def total_likes(self):
        return self.likes.count()

class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    reply = models.TextField(blank=True, null=True)
    replied_at = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return f"Comment by {self.user} on {self.post}"

class BentoReservation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reservations')
    reservation_date = models.DateField()
    side_dish = models.BooleanField(default=False)
    rice = models.BooleanField(default=False)
    rice_gram = models.IntegerField(null=True, blank=True)
    received = models.BooleanField(default=False)
    memo = models.TextField(blank=True, null=True)
    transfer_user = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.user} - {self.reservation_date}"
    
    @property
    def can_cancel(self):
        cancel_deadline = self.reservation_date - timedelta(days=1)
        cancel_deadline_time = timezone.make_aware(datetime.combine(cancel_deadline, time(15, 0, 0)))
        return timezone.now() < cancel_deadline_time
    
    def __str__(self):
        return f'{self.user.username} - {self.reservation_date}'

class BentoUnavailableDay(models.Model):
    date = models.DateField()
    reason = models.CharField(max_length=255, blank=True)  # 休日の理由や説明

    def __str__(self):
        return str(self.date)

class MenuUpload(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='menus/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title