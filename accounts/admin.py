from django.contrib import admin, messages
from .models import Post, Comment, BentoReservation, BentoUnavailableDay
from django.urls import path
from django.shortcuts import render
from django.utils import timezone
from datetime import datetime

class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0

class PostAdmin(admin.ModelAdmin):
    inlines = [CommentInline]
    list_display = ('title', 'created_at', 'total_likes', 'has_new_comments')
    prepopulated_fields = {'slug': ('title', )}
    
    # 既読ユーザーの「姓」と「名」を表示
    def get_read_users(self, obj):
        return ", ".join([f"{user.last_name} {user.first_name}" for user in obj.read_by.all()])
    get_read_users.short_description = '既読ユーザー'

    
    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('likes')

    def liked_users(self, obj):
        return ', '.join([f'{user.last_name} {user.first_name}' for user in obj.likes.all()])
    liked_users.short_description = '興味ありユーザー'
    
    def has_new_comments(self, obj):
        return obj.comments.filter(reply__isnull=True).exists()
    has_new_comments.boolean = True
    has_new_comments.short_description = 'New Comments'
    
    readonly_fields = ('get_read_users', 'liked_users', )

class CommentAdmin(admin.ModelAdmin):
    list_display = ('user', 'post', 'created_at', 'reply', 'replied_at')
    search_fields = ('post', 'user')
    
    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return ['reply', 'replied_at']
        return super().get_readonly_fields(request, obj)
    
class BentoReservationAdmin(admin.ModelAdmin):
    list_display = ('user__last_name', 'user__first_name', 'reservation_date', 'side_dish', 'rice', 'rice_gram', 'received', 'transfer_user')
    list_filter = ('reservation_date', 'received')
    search_fields = ('user__username', 'user__last_name', 'user__first_name', 'reservation_date', 'memo')
    ordering = ('-reservation_date',)

    def changelist_view(self, request, extra_context=None):
        # 日付フィルタで絞り込まれたクエリセットを取得
        queryset = self.get_queryset(request)
        
        # 集計のデバッグメッセージ
        print(f"集計デバッグ: {queryset.count()}件の予約データがフィルタされています")

        # フィルタされたデータに基づいて集計を行う
        side_dish_count = queryset.filter(side_dish=True).count()
        rice_100g_count = queryset.filter(rice=True, rice_gram=100).count()
        rice_160g_count = queryset.filter(rice=True, rice_gram=160).count()
        rice_200g_count = queryset.filter(rice=True, rice_gram=200).count()

        # 追加のデバッグメッセージ
        print(f"おかず: {side_dish_count}, ごはん100g: {rice_100g_count}, ごはん160g: {rice_160g_count}, ごはん200g: {rice_200g_count}")

        # 集計データをテンプレートに渡す
        extra_context = extra_context or {}
        extra_context['side_dish_count'] = side_dish_count
        extra_context['rice_100g_count'] = rice_100g_count
        extra_context['rice_160g_count'] = rice_160g_count
        extra_context['rice_200g_count'] = rice_200g_count

        return super().changelist_view(request, extra_context=extra_context)
    
    def get_queryset(self, request):
        # 管理者用に予約一覧を表示するためのクエリセット
        qs = super().get_queryset(request)
        return qs

    def save_model(self, request, obj, form, change):
        # 保存時にカスタム処理が必要であれば記述
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        # 管理者が新しい予約を追加することを禁止する場合、ここで制御
        return False

    def has_delete_permission(self, request, obj=None):
        # 管理者が予約を削除できないようにする場合
        return False


class BentoUnavailableDayAdmin(admin.ModelAdmin):
    list_display = ['date', 'reason']

admin.site.register(BentoReservation, BentoReservationAdmin)
admin.site.register(BentoUnavailableDay, BentoUnavailableDayAdmin)

admin.site.register(Post, PostAdmin) 