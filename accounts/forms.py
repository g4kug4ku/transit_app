from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Comment, BentoReservation, BentoUnavailableDay
from django.utils import timezone
import jpholiday
import datetime
from django.core.exceptions import ValidationError
from datetime import date

class SignUpForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)
    
    class Meta:
        model =User
        fields = ('username', 'first_name', 'last_name', 'password1', 'password2')

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'placeholder': 'コメントを入力...'})
        }
        labels = {
            'content': '',
        }        

class BentoReservationForm(forms.ModelForm):
    class Meta:
        model = BentoReservation
        fields = ['reservation_date', 'side_dish', 'rice', 'rice_gram']

    def __init__(self, *args, **kwargs):
        # requestを初期化メソッドで受け取る
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        side_dish = cleaned_data.get('side_dish', False)
        rice = cleaned_data.get('rice', False)
        rice_gram = cleaned_data.get('rice_gram')

        # おかずかごはんのどちらも選択されていない場合にエラーを表示
        if not side_dish and not rice:
            raise ValidationError("おかずまたはごはんを選択してください。")

        # ごはんを選択した場合、グラム数が選択されていないとエラー
        if rice and not rice_gram:
            raise ValidationError("ごはんのグラム数を選択してください。")

        return cleaned_data

    def clean_reservation_date(self):
        reservation_date = self.cleaned_data.get('reservation_date')
        unavailable_days = BentoUnavailableDay.objects.values_list('date', flat=True)
        
        # ここでrequest.userを参照
        user = self.request.user if self.request else None
        
        if not user:
            raise ValidationError("ユーザー情報が見つかりません。")

        # 重複した予約を防ぐ
        if BentoReservation.objects.filter(user=user, reservation_date=reservation_date).exists():
            raise ValidationError("すでにこの日に予約があります。別の日を選んでください。")
        
        # 日付が土日祝日や無効な場合にエラーを出すロジックを追加
        if reservation_date.weekday() >= 5 or jpholiday.is_holiday(reservation_date):
            raise ValidationError("土日祝日は予約できません。")
        
        if reservation_date in unavailable_days:
            raise ValidationError("選択した日は予約不可です。別の日を選択してください。")
        
        # 前日の15時を過ぎたら予約できないロジック
        today = timezone.localdate()
        if reservation_date == today + datetime.timedelta(days=1):
            cancel_deadline = datetime.datetime.combine(today, datetime.time(16, 0, 0))
            if timezone.now() > timezone.make_aware(cancel_deadline):
                raise ValidationError("翌日分の予約は前日の16時までです。")
        
        # 予約日が過去の日付でないかのチェック (任意で追加)
        if reservation_date < date.today():
            raise ValidationError("過去の日付は予約できません。")
        
        # 未来の日付に既に予約があるか確認（当日の予約は許可）
        if reservation_date > today:
            if BentoReservation.objects.filter(user=user, reservation_date__gte=today).exclude(reservation_date=today).exists():
                raise forms.ValidationError("既に未来の予約があります。新しい予約を行うには、前回の予約を取り消してください。")

        return reservation_date