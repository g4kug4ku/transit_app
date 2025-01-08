from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm, CommentForm, BentoReservationForm, MenuUploadForm, KakeiboForm, SongRequestForm
from .models import Post, Comment, BentoReservation, BentoUnavailableDay, User, MenuUpload, KakeiboEntry, SongRequest
from django.urls import resolve, reverse
from .utils import decode_filename
from django.contrib import messages
from datetime import datetime, timedelta
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.db.models import Q, Sum, Count
from collections import defaultdict
from django.utils.timezone import localdate
from itertools import groupby
from operator import attrgetter
from django.views.decorators.csrf import csrf_exempt
import json
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
import os
from django.conf import settings

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
    cancel_deadline = datetime.combine(cancel_deadline, datetime.min.time()).replace(hour=17)

    # 現在の日時が取り消し期限より前かを確認
    if datetime.now() < cancel_deadline:
        reservation.delete()  # 予約を取り消す
        messages.success(request, "予約を取り消しました。")
    else:
        messages.error(request, "予約を取り消せるのは前日の17時までです。")

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

def export_bento_reservations(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    reservations_by_date = BentoReservation.objects.filter(
        reservation_date__range=[start_date, end_date]
    ).order_by('reservation_date')

    # Excelファイルを作成
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Reservations"

    # ヘッダーのテキストを追加 (1行目)
    header_text = f"{start_date}から{end_date}分 弁当予約者一覧"
    ws.merge_cells('A1:F1')  # ヘッダーテキスト用の結合セル
    header_cell = ws['A1']
    header_cell.value = header_text
    header_cell.font = Font(size=16, bold=True)
    header_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 30

    # ヘッダーを2行目に追加
    headers = ["日付", "氏名", "ごはん", "おかず", "受取済", "振替元"]
    ws.append(headers)

    # ヘッダーのスタイル設定
    for col_num, header in enumerate(headers, start=1):
        cell = ws.cell(row=2, column=col_num)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
        cell.alignment = Alignment(horizontal="center", vertical="center")

    # データを3行目から追加
    row_num = 3
    for reservation in reservations_by_date:
        ws.append([
            reservation.reservation_date.strftime("%Y-%m-%d"),
            f"{reservation.user.last_name} {reservation.user.first_name}",
            f"{reservation.rice_gram}g" if reservation.rice else "なし",
            "あり" if reservation.side_dish else "なし",
            "はい" if reservation.received else "いいえ",
            reservation.original_user_name or "なし"
        ])
        row_num += 1

    # 固定幅設定: 日付列の幅を狭くする (例: 15文字幅)
    ws.column_dimensions['A'].width = 15  # 日付列
    # 他の列の自動調整
    for col in ws.iter_cols(min_col=2, max_col=len(headers)):
        max_length = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max_length + 6

    # 枠線を追加
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin")
    )
    for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=len(headers)):
        for cell in row:
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center", vertical="center")

    # フィルターをヘッダー行に追加（2行目にフィルター適用）
    ws.auto_filter.ref = f"A2:F{ws.max_row}"

    # ファイル名に期間を動的に設定
    filename = f"reservations_{start_date}_to_{end_date}.xlsx"

    # レスポンスにExcelファイルを追加
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response

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
    file_path = os.path.join(settings.MEDIA_ROOT, str(menu.file))
    menu.delete()
    # ファイルが存在する場合は削除
    if os.path.exists(file_path):
        os.remove(file_path)
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
        grouped_entries[entry.created_at].append(entry)

    total_income = entries.filter(transaction_type='income').aggregate(total=Sum('amount'))['total'] or 0
    total_expense = entries.filter(transaction_type='expense').aggregate(total=Sum('amount'))['total'] or 0

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
    income_categories = ['給与', '副収入', '投資収益', '臨時収入', '不労所得', '返金・補助金', 'その他（収入）']
    expense_categories = ['住居費', '食費', '光熱費', '通信費', '交通費', '保険料', '教育費', '医療費', '娯楽費', '衣服・美容', '交際費', '税金・手数料', 'その他（支出）']

    if request.method == 'POST':
        form = KakeiboForm(request.POST, request.FILES, instance=entry)
        if form.is_valid():
            # 画像削除のチェックが入っている場合
            if 'delete_image' in request.POST and request.POST['delete_image'] == 'on':
                if entry.image:
                    entry.image.delete()  # 画像ファイルを削除
                    entry.image = None  # フィールドを空にする

            form.save()
            messages.success(request, "家計簿が更新されました！")
            return redirect('kakeibo_list')
    else:
        form = KakeiboForm(instance=entry)

    return render(request, 'accounts/kakeibo_detail.html', {
        'entry': entry,
        'income_categories': income_categories,
        'expense_categories': expense_categories,
    })

@login_required
def kakeibo_create(request):
    if request.method == 'POST':
        form = KakeiboForm(request.POST, request.FILES)
        if form.is_valid():
            form.instance.user = request.user  # ユーザー情報を設定
            form.instance.created_at = form.cleaned_data['created_at']
            form.save()  # データベースに保存
            messages.success(request, "収支が追加されました！")
            return redirect('kakeibo_list')  # 保存後にリストページへリダイレクト
        else:
            # フォームが無効な場合、エラーを表示
            messages.error(request, "入力にエラーがあります。確認してください。")
    else:
        form = KakeiboForm()

    return render(request, 'accounts/kakeibo_form.html', {'form': form})

@login_required
def kakeibo_delete(request, pk):
    entry = get_object_or_404(KakeiboEntry, pk=pk, user=request.user)
    entry.delete()
    messages.success(request, "収支データを削除しました！")
    return redirect('kakeibo_list')

#曲リクエスト
@login_required
def song_request_list(request):
    sort = request.GET.get('sort', 'date')  # デフォルトは日付順
    if sort == 'likes':
        requests = SongRequest.objects.annotate(like_count=Count('likes')).order_by('-like_count')
    else:
        requests = SongRequest.objects.order_by('-request_date')
    return render(request, 'accounts/song_request_list.html', {'requests': requests, 'sort': sort})

@login_required
@csrf_exempt  # AJAXリクエスト用
def song_request_create(request):
    if request.method == 'POST':
        data = json.loads(request.body)  # JSONデータを取得
        artist = data.get('artist')
        song_name = data.get('song_name')

        if artist and song_name:
            song_request = SongRequest.objects.create(
                user=request.user,
                artist=artist,
                song_name=song_name
            )
            return JsonResponse({
                'id': song_request.id,
                'artist': song_request.artist,
                'song_name': song_request.song_name,
                'request_date': song_request.request_date.strftime('%Y-%m-%d'),
                'user': f"{song_request.user.last_name} {song_request.user.first_name}",
                'like_count': 0
            })
        return JsonResponse({'error': 'Invalid data'}, status=400)

@login_required
def toggle_like(request, request_id):
    if request.method == 'POST':
        song_request = get_object_or_404(SongRequest, id=request_id)
        if request.user in song_request.likes.all():
            song_request.likes.remove(request.user)
            liked = False
        else:
            song_request.likes.add(request.user)
            liked = True
        song_request.save()
        return JsonResponse({'liked': liked, 'like_count': song_request.likes.count()})
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def delete_song_request(request, request_id):
    song_request = get_object_or_404(SongRequest, id=request_id, user=request.user)
    song_request.delete()
    return JsonResponse({'success': True})