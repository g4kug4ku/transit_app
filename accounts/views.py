from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm, CommentForm, BentoReservationForm, MenuUploadForm, KakeiboForm
from .models import Post, Comment, BentoReservation, BentoUnavailableDay, User, MenuUpload, KakeiboEntry
from django.urls import resolve, reverse
from .utils import decode_filename
from django.contrib import messages
from datetime import datetime, timedelta
from django.utils import timezone
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.db.models import Q, Sum
from collections import defaultdict
from django.utils.timezone import localdate
from itertools import groupby
from operator import attrgetter

# Create your views here.
def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = SignUpForm()
    return render(request, 'accounts/signup.html', {'form': form})

@login_required
def index(request):
    posts = Post.objects.all().order_by('-created_at')
    return render(request, 'accounts/index.html', {'posts': posts})

def post_list(request):
    posts = Post.objects.all()
    return render(request, 'accounts/post_list.html', {'posts': posts})


@login_required
def post_detail(request, slug):
    post = get_object_or_404(Post, slug=slug)
    
    # ユーザーがまだ既読でなければ追加
    if request.user not in post.read_by.all():
        post.read_by.add(request.user)
    
    
    comments = post.comments.all()
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.post = post
            comment.user = request.user
            comment.save()
            return redirect('post_detail', slug=post.slug)
    else:
        form = CommentForm()
    
    # 新規コメントのフラグを消す
    if post.new_comment:
        post.new_comment = False
        post.save()
            
    context = {
        'post': post,
        'decoded_file_url': decode_filename(post.attached_file.url) if post.attached_file else None,
        'comments': post.comments.all(),
        'form': form,
    }
        
    return render(request, 'accounts/post_detail.html', context)

@login_required
def like_post(request, slug):
    post = get_object_or_404(Post, slug=slug)
    if request.user in post.likes.all():
        post.likes.remove(request.user)  # Unlike the post
        liked = False
    else:
        post.likes.add(request.user)  # Like the post
        liked = True
    return JsonResponse({'liked': liked, 'total_likes': post.total_likes()})

@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    if request.method == 'POST':
        content = request.POST.get('content')
        comment = Comment.objects.create(post=post, user=request.user, content=content)
        post.new_comment = True
        post.save()
    return redirect('post_detail', slug=post.slug)

@login_required
def bento_reservation(request):
    if request.method == 'POST':
        form = BentoReservationForm(request.POST, request=request)  # requestを渡す
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.user = request.user
            reservation.save()
            messages.success(request, "予約が完了しました。")
            return redirect('reservation_list')
    else:
        form = BentoReservationForm(request=request)  # GETリクエスト時もrequestを渡す
    
    
    latest_menu = MenuUpload.objects.last()
    
    # 献立が存在し、PDFかどうかをチェック
    is_pdf = False
    if latest_menu and latest_menu.file.url.endswith(".pdf"):
        is_pdf = True
    
    return render(request, 'accounts/bento_reservation.html', {'form': form, 'latest_menu': latest_menu, 'is_pdf': is_pdf})

@login_required
def reservation_list(request):
    # 絞り込み機能：期間を指定してフィルター
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    today = timezone.localdate()  # 現在の日付を取得

    reservations = BentoReservation.objects.filter(user=request.user)

    # 絞り込み条件が指定されている場合
    if start_date:
        reservations = reservations.filter(reservation_date__gte=start_date)
    if end_date:
        reservations = reservations.filter(reservation_date__lte=end_date)

    # 降順で予約を表示
    reservations = reservations.order_by('-reservation_date')

    return render(request, 'accounts/reservation_list.html', {
        'reservations': reservations,
        'start_date': start_date,
        'end_date': end_date,
        'today': today,  # テンプレートに渡す
    })

def cancel_reservation(request, reservation_id):
    reservation = get_object_or_404(BentoReservation, id=reservation_id, user=request.user)
    
    # 予約日の前日の16時を取得
    cancel_deadline = reservation.reservation_date - timedelta(days=1)
    cancel_deadline = datetime.combine(cancel_deadline, datetime.min.time()).replace(hour=16)

    # 現在の日時が取り消し期限より前かを確認
    if datetime.now() < cancel_deadline:
        reservation.delete()  # 予約を取り消す
        messages.success(request, "予約を取り消しました。")
    else:
        messages.error(request, "予約を取り消せるのは前日の16時までです。")

    return redirect('reservation_list')

def receive_bento(request, reservation_id):
    reservation = get_object_or_404(BentoReservation, id=reservation_id)
    if not reservation.received:
        reservation.received = True
        reservation.save()
    return redirect(reverse('reservation_list'))

def admin_bento_reservation_list(request):
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    reservations_by_date = {}  # 日付ごとの予約内容を格納する辞書

    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # 指定された期間の予約を取得
        for n in range((end_date - start_date).days + 1):
            current_date = start_date + timedelta(n)
            reservations = BentoReservation.objects.filter(reservation_date=current_date)
            reservations_by_date[current_date] = reservations

    # 各日の合計数を集計
    side_dish_counts = {}
    rice_100g_counts = {}
    rice_160g_counts = {}
    rice_200g_counts = {}

    for date, reservations in reservations_by_date.items():
        side_dish_counts[date] = reservations.filter(side_dish=True).count()
        rice_100g_counts[date] = reservations.filter(rice=True, rice_gram=100).count()
        rice_160g_counts[date] = reservations.filter(rice=True, rice_gram=160).count()
        rice_200g_counts[date] = reservations.filter(rice=True, rice_gram=200).count()

    return render(request, 'admin/admin_bento_reservation_list.html', {
        'reservations_by_date': reservations_by_date,
        'start_date': start_date_str,
        'end_date': end_date_str,
        'side_dish_counts': side_dish_counts,
        'rice_100g_counts': rice_100g_counts,
        'rice_160g_counts': rice_160g_counts,
        'rice_200g_counts': rice_200g_counts,
    })






def create_reservation(request):
    if request.method == 'POST':
        form = BentoReservationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('reservation_list')
        else:
            # フォームが無効な場合、エラーを含んだ状態で再度フォームを表示
            return render(request, 'bento_reservation.html', {'form': form})
    else:
        form = BentoReservationForm()

    return render(request, 'bento_reservation.html', {'form': form})

def generate_order_sheet(request):
    side_dish = request.GET.get('side_dish', 0)
    rice_100g = request.GET.get('rice_100g', 0)
    rice_160g = request.GET.get('rice_160g', 0)
    rice_200g = request.GET.get('rice_200g', 0)
    date = request.GET.get('date', '')

    # デバッグ用のプリント
    print(f"おかず: {side_dish}, 100g: {rice_100g}, 160g: {rice_160g}, 200g: {rice_200g}")
    
    context = {
        'side_dish': side_dish,
        'rice_100g': rice_100g,
        'rice_160g': rice_160g,
        'rice_200g': rice_200g,
        'date': date,
    }

    return render(request, 'accounts/order_sheet.html', context)

@login_required
def upload_menu(request):
    if request.method == 'POST':
        form = MenuUploadForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return redirect('upload_menu')
    else:
        form = MenuUploadForm()

    # 既存のメニューを取得
    menus = MenuUpload.objects.all()

    return render(request, 'accounts/menu.html', {'form': form, 'menus': menus})

@login_required
def delete_menu(request, menu_id):
    menu = get_object_or_404(MenuUpload, id=menu_id)
    menu.delete()
    messages.success(request, '献立が削除されました。')
    return redirect('upload_menu')

#家計簿
import logging

logger = logging.getLogger(__name__)

@login_required
def kakeibo_list(request):
    current_year = request.GET.get("year", localdate().year)
    current_month = request.GET.get("month", localdate().month)

    entries = KakeiboEntry.objects.filter(
        user=request.user,
        created_at__year=current_year,
        created_at__month=current_month,
    ).order_by('-created_at')

    # デバッグ用ログ
    logger.info(f"Selected Year: {current_year}, Selected Month: {current_month}")
    logger.info(f"Entries: {entries}")

    grouped_entries = defaultdict(list)
    for entry in entries:
        grouped_entries[entry.created_at.date()].append(entry)

    total_income = entries.filter(transaction_type="income").aggregate(Sum("amount"))["amount__sum"] or 0
    total_expense = entries.filter(transaction_type="expense").aggregate(Sum("amount"))["amount__sum"] or 0

    return render(request, 'accounts/kakeibo_list.html', {
        "grouped_entries": dict(grouped_entries),
        "total_income": total_income,
        "total_expense": total_expense,
        "current_year": int(current_year),
        "current_month": int(current_month),
        "month_range": range(1, 13),
        "year_range": range(localdate().year - 5, localdate().year + 1),  # 5年前から今年まで
    })

@login_required
def kakeibo_detail(request, pk):
    entry = get_object_or_404(KakeiboEntry, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = KakeiboForm(request.POST, request.FILES, instance=entry)
        if form.is_valid():
            if 'delete_image' in request.POST and request.POST['delete_image'] == 'on':
                entry.image.delete(save=False)  # 画像を削除
                entry.image = None
            form.save()
            messages.success(request, "収支情報が更新されました！")
            return redirect('kakeibo_list')
    else:
        form = KakeiboForm(instance=entry)
    
    return render(request, 'accounts/kakeibo_detail.html', {'form': form, 'entry': entry})

@login_required
def kakeibo_create(request):
    if request.method == 'POST':
        form = KakeiboForm(request.POST, request.FILES)
        if form.is_valid():
            # ログインユーザーを設定
            form.instance.user = request.user
            form.save()
            messages.success(request, "収支が追加されました！")
            return redirect('kakeibo_list')  # 保存後に一覧ページにリダイレクト
        else:
            messages.error(request, "入力内容に誤りがあります。")
    else:
        form = KakeiboForm()

    return render(request, 'accounts/kakeibo_form.html', {'form': form})

@login_required
def kakeibo_delete(request, pk):
    entry = get_object_or_404(KakeiboEntry, pk=pk, user=request.user)
    entry.delete()
    messages.success(request, "収支データを削除しました！")
    return redirect('kakeibo_list')
