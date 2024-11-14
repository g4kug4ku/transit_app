from django.contrib import admin, messages
from .models import Post, Comment, BentoReservation, BentoUnavailableDay, UserChangeLog
from .forms import CustomUserChoiceField
from django.urls import path
from django.shortcuts import render
from django.utils import timezone
from datetime import datetime
from django.utils.safestring import mark_safe
from django.contrib.auth import get_user_model

User = get_user_model()

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
    list_display = ('get_user_full_name', 'reservation_date_jp', 'side_dish_jp', 'rice_jp', 'rice_gram_jp', 'received_jp', 'original_user_full_name')
    list_filter = ('reservation_date', 'received')
    search_fields = ('user__username', 'user__last_name', 'user__first_name', 'reservation_date', 'memo')
    ordering = ('-reservation_date',)
    readonly_fields = ('previous_user_name',)
    
    def get_user_full_name(self, obj):
        return f"{obj.user.last_name} {obj.user.first_name}"
    get_user_full_name.short_description = 'ユーザー'  # 列ヘッダーの表示名
    
    def reservation_date_jp(self, obj):
        return obj.reservation_date
    reservation_date_jp.short_description = "予約日"

    def side_dish_jp(self, obj):
        return "あり" if obj.side_dish else "なし"
    side_dish_jp.short_description = "おかず"

    def rice_jp(self, obj):
        return "あり" if obj.rice else "なし"
    rice_jp.short_description = "ごはん"

    def rice_gram_jp(self, obj):
        return f"{obj.rice_gram}g" if obj.rice else ""
    rice_gram_jp.short_description = "ごはんのグラム数"

    def received_jp(self, obj):
        return "はい" if obj.received else "いいえ"
    received_jp.short_description = "受け取り済"
    
    
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user":
            kwargs["form_class"] = CustomUserChoiceField
            kwargs["queryset"] = User.objects.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def previous_user_name(self, obj):
        if obj and obj.user:
            # フルネームを表示
            return f"{obj.user.last_name} {obj.user.first_name}"
        return "No User Selected"

    previous_user_name.short_description = "Previous User Name"
    
    def save_model(self, request, obj, form, change):
        if change:
            if 'user' in form.changed_data:
                # ユーザーが変更された場合、変更履歴を追加
                previous_user = BentoReservation.objects.get(pk=obj.pk).user
                UserChangeLog.objects.create(
                    reservation=obj,
                    old_user=previous_user,
                    new_user=obj.user,
                    changed_at=timezone.now()
                )
        super().save_model(request, obj, form, change)

    def previous_user_name(self, obj):
        if obj:
            logs = obj.change_logs.order_by('-changed_at')  # 変更履歴を最新順に取得
            history = []
            for log in logs:
                old_name = f"{log.old_user.last_name} {log.old_user.first_name}" if log.old_user else "No User"
                new_name = f"{log.new_user.last_name} {log.new_user.first_name}" if log.new_user else "No User"
                timestamp = log.changed_at.strftime("%Y年%m月%d日(%a) %H:%M")
                history.append(f"{timestamp}　{old_name} から {new_name} に変更")
            return "<br>".join(history)
        return "No Change History"

    previous_user_name.short_description = "Change History"
    previous_user_name.allow_tags = True
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name in ["user", "transfer_user", "original_user"]:
            kwargs["form_class"] = CustomUserChoiceField
            kwargs["queryset"] = User.objects.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
    
    def original_user_full_name(self, obj):
        # 変更前の元のユーザーのフルネームを表示
        if obj.original_user:
            return f"{obj.original_user.last_name} {obj.original_user.first_name}"
        return "振替なし"
    original_user_full_name.short_description = '振替元'

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



class BentoUnavailableDayAdmin(admin.ModelAdmin):
    list_display = ['date', 'reason']

admin.site.register(BentoReservation, BentoReservationAdmin)
admin.site.register(BentoUnavailableDay, BentoUnavailableDayAdmin)
admin.site.register(Post, PostAdmin) 