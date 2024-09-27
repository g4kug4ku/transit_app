from django.contrib import admin
from .models import Post, PostView

@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'created_at']

    def interested_users_list(self, obj):
        return ", ".join([f"{user.last_name} {user.first_name}" for user in obj.interested_users.all()])

    interested_users_list.short_description = '興味有ユーザー'
    fields = ['title', 'content', 'created_at', 'interested_users_list']