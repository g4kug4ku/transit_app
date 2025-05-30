from django.db import models
from django.contrib.auth.models import User
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify
from datetime import timedelta, datetime, time, date
from django.conf import settings

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

    class Meta:
        verbose_name = "投稿"
        verbose_name_plural = "投稿一覧"

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
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reservations', verbose_name='予約者')
    reservation_date = models.DateField(verbose_name='予約日')
    side_dish = models.BooleanField(default=False, verbose_name='おかず')
    rice = models.BooleanField(default=False, verbose_name='ごはん')
    rice_gram = models.IntegerField(null=True, blank=True, verbose_name='グラム数')
    received = models.BooleanField(default=False)
    memo = models.TextField(blank=True, null=True)
    transfer_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='transferred_reservations', verbose_name='振替先')
    original_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='original_reservations', verbose_name='振替元')
    created_at = models.DateTimeField(auto_now_add=True, null=True)  # null=True を追加

    def __str__(self):
        return f"{self.user} - {self.reservation_date}"

    @property
    def can_cancel(self):
        cancel_deadline = self.reservation_date - timedelta(days=1)
        cancel_deadline_time = timezone.make_aware(datetime.combine(cancel_deadline, time(15, 0, 0)))
        return timezone.now() < cancel_deadline_time

    @property
    def transfer_user_name(self):
        if self.transfer_user:
            return f"{self.transfer_user.last_name} {self.transfer_user.first_name}"
        return "No Transfer User"

    @property
    def original_user_name(self):
        if self.original_user:
            return f"{self.original_user.last_name} {self.original_user.first_name}"
        return "No Original User"

    def __str__(self):
        return f'{self.user.username} - {self.reservation_date}'

    class Meta:
        verbose_name = "弁当予約"
        verbose_name_plural = "弁当予約一覧"

class UserChangeLog(models.Model):
    reservation = models.ForeignKey(BentoReservation, on_delete=models.CASCADE, related_name='change_logs')
    old_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='old_user_logs')
    new_user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='new_user_logs')
    changed_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.changed_at} - {self.old_user} to {self.new_user}"

class BentoUnavailableDay(models.Model):
    date = models.DateField()
    reason = models.CharField(max_length=255, blank=True)  # 休日の理由や説明

    def __str__(self):
        return str(self.date)

    class Meta:
        verbose_name = "予約不可日"
        verbose_name_plural = "予約不可日一覧"

class MenuUpload(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='menus/')
    url = models.URLField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

#家計簿
class KakeiboEntry(models.Model):
    TRANSACTION_TYPE_CHOICES = [
        ('income', '収入'),
        ('expense', '支出'),
    ]

    STATUS_CHOICES = [
        ('confirmed', '確定済み'),
        ('pending', '未確定'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    transaction_type = models.CharField(
        max_length=10,
        choices=TRANSACTION_TYPE_CHOICES,
        default='expense'
    )
    category = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending'
    )
    memo = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='kakeibo_images/', blank=True, null=True)
    created_at = models.DateField()  # 作成日時
    updated_at = models.DateTimeField(auto_now=True)      # 更新日時

    def __str__(self):
        return f"{self.user.username} - {self.category} ({self.transaction_type})"

#曲リクエスト
class SongRequest(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    artist = models.CharField(max_length=100)
    song_name = models.CharField(max_length=100)
    request_date = models.DateTimeField(auto_now_add=True)
    likes = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='liked_requests', blank=True)

    def like_count(self):
        return self.likes.count()

    def __str__(self):
        return f"{self.song_name} - {self.artist}"

#映画
class FavoriteMovies(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorite_movies')
    rank_3 = models.CharField(max_length=255, verbose_name="第3位の映画")
    reason_3 = models.TextField(verbose_name="第3位の理由")
    rank_2 = models.CharField(max_length=255, verbose_name="第2位の映画")
    reason_2 = models.TextField(verbose_name="第2位の理由")
    rank_1 = models.CharField(max_length=255, verbose_name="第1位の映画")
    reason_1 = models.TextField(verbose_name="第1位の理由")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}'s Favorite Movies"

class FavoriteMoviesComment(models.Model):
    favorite_movies = models.ForeignKey(FavoriteMovies, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField(verbose_name="コメント内容")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user.username} on {self.favorite_movies}"

#bbs
class BBSPost(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bbs_posts")
    title = models.CharField(max_length=255)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class BBSComment(models.Model):
    post = models.ForeignKey(BBSPost, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    parent_comment = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')

    def __str__(self):
        return f"{self.user.username} - {self.content[:20]}"