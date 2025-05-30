from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Comment, BentoReservation, BentoUnavailableDay, MenuUpload, KakeiboEntry, SongRequest, FavoriteMovies, FavoriteMoviesComment, BBSPost, BBSComment
from django.utils import timezone
import jpholiday
import datetime
from django.core.exceptions import ValidationError
from datetime import datetime, timedelta, date, time

User = get_user_model()

class SignUpForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model =User
        fields = ('username', 'first_name', 'last_name', 'password1', 'password2')

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("設定したユーザー名は既に使われています。")
        return username

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        username = self.cleaned_data.get('username')

        if password1 and username and password1 == username:
            raise ValidationError("パスワードはユーザー名と別のものにしてください。")

        return password2

class CustomUserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.last_name} {obj.first_name}"

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
        current_datetime = timezone.now()

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

        # 前日の17時を過ぎたら予約できないロジック表記上は17時までだが設定は18時まで
        today = timezone.localdate()
        """
        期限一時停止
        if reservation_date == today + timedelta(days=1):
            cancel_deadline = datetime.combine(today, time(18, 0))
            if timezone.now() > timezone.make_aware(cancel_deadline):
                raise ValidationError("翌日分の予約は前日の17時までです。")
        """

        # 予約日が過去の日付でないかのチェック (任意で追加)
        if reservation_date < date.today():
            raise ValidationError("過去の日付は予約できません。")

        if reservation_date == date.today():
            raise ValidationError('当日は予約できません。')

        # 翌週の最初の平日を計算
        next_weekday = reservation_date
        while next_weekday.weekday() in [5, 6] or BentoUnavailableDay.objects.filter(date=next_weekday).exists():
            next_weekday += timedelta(days=1)

        # 前の週の最後の平日を計算
        previous_weekday = next_weekday - timedelta(days=1)
        while previous_weekday.weekday() in [5, 6] or BentoUnavailableDay.objects.filter(date=previous_weekday).exists():
            previous_weekday -= timedelta(days=1)

        reservation_deadline = timezone.make_aware(datetime.combine(previous_weekday, time(23, 0)))

        if reservation_date == next_weekday and current_datetime > reservation_deadline:
            raise ValidationError(f"{next_weekday.strftime('%Y-%m-%d')} の予約は {previous_weekday.strftime('%Y-%m-%d')} の17時までです。")

        # 未来の日付に既に予約があるか確認（当日の予約は許可）
        if reservation_date > today:
            if BentoReservation.objects.filter(user=user, reservation_date__gte=today).exclude(reservation_date=today).exists():
                raise forms.ValidationError("既に未来の予約があります。新しい予約を行うには、前回の予約を取り消してください。")

        return reservation_date

class MenuUploadForm(forms.ModelForm):
    class Meta:
        model = MenuUpload
        fields = ['title', 'file', 'url']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].required = False
        self.fields['url'].required = False

    def clean(self):
        cleaned_data = super().clean()
        file = self.cleaned_data.get('file')
        url = cleaned_data.get('url')
        if not file and not url:
            raise forms.ValidationError("ファイルまたはURLのどちらかを入力してください。")
        if file and url:
            raise forms.ValidationError("ファイルとURLは同時に指定できません。どちらか一方にしてください。")
        return cleaned_data

#家計簿
class KakeiboForm(forms.ModelForm):
    class Meta:
        model = KakeiboEntry
        fields = ['created_at', 'transaction_type', 'category', 'amount', 'status', 'memo', 'image']
        widgets = {
            'created_at': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'transaction_type': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'memo': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
        }

    INCOME_CATEGORIES = [
        ('給与', '給与'), ('副収入', '副収入'), ('投資収益', '投資収益'),
        ('臨時収入', '臨時収入'), ('不労所得', '不労所得'),
        ('返金・補助金', '返金・補助金'), ('その他（収入）', 'その他（収入）')
    ]

    EXPENSE_CATEGORIES = [
        ('住居費', '住居費'), ('食費', '食費'), ('光熱費', '光熱費'),
        ('通信費', '通信費'), ('交通費', '交通費'), ('保険料', '保険料'),
        ('教育費', '教育費'), ('医療費', '医療費'), ('娯楽費', '娯楽費'),
        ('衣服・美容', '衣服・美容'), ('交際費', '交際費'),
        ('税金・手数料', '税金・手数料'), ('その他（支出）', 'その他（支出）')
    ]

    def __init__(self, *args, **kwargs):
        super(KakeiboForm, self).__init__(*args, **kwargs)
        self.fields['category'].choices = [('', 'カテゴリを選択')]  # 初期値を設定

        if 'transaction_type' in self.data:
            transaction_type = self.data.get('transaction_type')
            if transaction_type == 'income':
                self.fields['category'].choices += self.INCOME_CATEGORIES
            elif transaction_type == 'expense':
                self.fields['category'].choices += self.EXPENSE_CATEGORIES
        elif self.instance and self.instance.transaction_type:
            # 編集時のカテゴリ設定
            if self.instance.transaction_type == 'income':
                self.fields['category'].choices += self.INCOME_CATEGORIES
            elif self.instance.transaction_type == 'expense':
                self.fields['category'].choices += self.EXPENSE_CATEGORIES

#曲リクエスト
class SongRequestForm(forms.ModelForm):
    class Meta:
        model = SongRequest
        fields = ['artist', 'song_name']
        widgets = {
            'artist': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'アーティスト名'}),
            'song_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '曲名'}),
        }

    def clean_song_name(self):
        song_name = self.cleaned_data.get('song_name')
        if SongRequest.objects.filter(song_name=song_name).exists():
            raise forms.ValidationError("すでにこの曲はリクエストされています。")
        return song_name

#映画
class FavoriteMoviesForm(forms.ModelForm):
    class Meta:
        model = FavoriteMovies  # モデルを指定
        fields = ['rank_3', 'reason_3', 'rank_2', 'reason_2', 'rank_1', 'reason_1']
        labels = {
            'rank_3': '第3位の映画',
            'reason_3': '第3位の理由',
            'rank_2': '第2位の映画',
            'reason_2': '第2位の理由',
            'rank_1': '第1位の映画',
            'reason_1': '第1位の理由',
        }
        widgets = {
            'reason_3': forms.Textarea(attrs={'class': 'form-control textarea-large'}),
            'reason_2': forms.Textarea(attrs={'class': 'form-control textarea-large'}),
            'reason_1': forms.Textarea(attrs={'class': 'form-control textarea-large'}),
        }

class FavoriteMoviesCommentForm(forms.ModelForm):
    class Meta:
        model = FavoriteMoviesComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class BBSPostForm(forms.ModelForm):
    class Meta:
        model = BBSPost
        fields = ["title", "content"]

class BBSCommentForm(forms.ModelForm):
    class Meta:
        model = BBSComment
        fields = ["content"]
        labels = {
            'content': '',  # ラベルを空にする
        }