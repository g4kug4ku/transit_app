from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm, CommentForm, BentoReservationForm
from .models import Post, Comment, BentoReservation, BentoUnavailableDay, User
from django.urls import resolve, reverse
from .utils import decode_filename
from django.http import JsonResponse
from django.contrib import messages
from datetime import datetime, timedelta
from django.utils import timezone
from django.http import HttpResponse
from django.template.loader import render_to_string

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
            reservation = form.save(commit=False)  # commit=Falseで一旦保存を遅らせる
            reservation.user = request.user  # 現在のユーザーを設定
            reservation.save()  # データベースに保存
            messages.success(request, "予約が完了しました。")
            return redirect('reservation_list')
    else:
        form = BentoReservationForm(request=request)  # GETリクエスト時もrequestを渡す
    
    return render(request, 'accounts/bento_reservation.html', {'form': form})

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
    
    # 予約日の前日の15時を取得
    cancel_deadline = reservation.reservation_date - timedelta(days=1)
    cancel_deadline = datetime.combine(cancel_deadline, datetime.min.time()).replace(hour=15)

    # 現在の日時が取り消し期限より前かを確認
    if datetime.now() < cancel_deadline:
        reservation.delete()  # 予約を取り消す
        messages.success(request, "予約を取り消しました。")
    else:
        messages.error(request, "予約を取り消せるのは前日の15時までです。")

    return redirect('reservation_list')

def receive_bento(request, reservation_id):
    reservation = get_object_or_404(BentoReservation, id=reservation_id)
    if not reservation.received:
        reservation.received = True
        reservation.save()
    return redirect(reverse('reservation_list'))

def admin_bento_reservation_list(request):
    selected_date = request.GET.get('selected_date', None)
    reservations = []
    side_dish_count = 0
    rice_100g_count = 0
    rice_160g_count = 0
    rice_200g_count = 0

    unavailable_days = BentoUnavailableDay.objects.all()  # 予約不可日を取得

    if selected_date:
        reservations = BentoReservation.objects.filter(reservation_date=selected_date)
        # おかずとごはんの数量集計
        side_dish_count = reservations.filter(side_dish=True).count()
        rice_100g_count = reservations.filter(rice=True, rice_gram=100).count()
        rice_160g_count = reservations.filter(rice=True, rice_gram=160).count()
        rice_200g_count = reservations.filter(rice=True, rice_gram=200).count()

    return render(request, 'admin/admin_bento_reservation_list.html', {
        'reservations': reservations,
        'selected_date': selected_date,
        'side_dish_count': side_dish_count,
        'rice_100g_count': rice_100g_count,
        'rice_160g_count': rice_160g_count,
        'rice_200g_count': rice_200g_count,
        'unavailable_days': unavailable_days,  # 予約不可日をテンプレートに渡す
    })



def admin_bento_reservation_list_view(request):
    selected_date_str = request.GET.get('selected_date') or request.POST.get('selected_date')
    reservations = []
    side_dish_count = 0
    rice_100g_count = 0
    rice_160g_count = 0
    rice_200g_count = 0

    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
            reservations = BentoReservation.objects.filter(reservation_date=selected_date)

            # おかずとごはんの数量集計
            side_dish_count = reservations.filter(side_dish=True).count()
            rice_100g_count = reservations.filter(rice=True, rice_gram=100).count()
            rice_160g_count = reservations.filter(rice=True, rice_gram=160).count()
            rice_200g_count = reservations.filter(rice=True, rice_gram=200).count()

        except ValueError:
            selected_date = None

    context = {
        'reservations': reservations,
        'selected_date': selected_date_str,
        'side_dish_count': side_dish_count,
        'rice_100g_count': rice_100g_count,
        'rice_160g_count': rice_160g_count,
        'rice_200g_count': rice_200g_count,
    }
    return render(request, 'accounts/admin_bento_reservation_list.html', context)

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
    selected_date = request.GET.get('selected_date', None)
    side_dish_count = request.GET.get('side_dish_count', 0)
    rice_100g_count = request.GET.get('rice_100g_count', 0)
    rice_160g_count = request.GET.get('rice_160g_count', 0)
    rice_200g_count = request.GET.get('rice_200g_count', 0)

    context = {
        'selected_date': selected_date,
        'side_dish_count': side_dish_count,
        'rice_100g_count': rice_100g_count,
        'rice_160g_count': rice_160g_count,
        'rice_200g_count': rice_200g_count,
    }

    return render(request, 'accounts/order_sheet.html', context)