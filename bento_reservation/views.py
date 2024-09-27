from django.shortcuts import render, redirect
from .forms import BentoReservationForm
from .models import BentoReservation
from django.utils import timezone

# Create your views here.
def reservation_view(request, date):
    if request.method == 'POST':
        form = BentoReservationForm(request.POST)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.user = request.user
            reservation.reservation_date = date
            reservation.save()
            return redirect('bento_reservation:reservation_success')
        else:
            form = BentoReservationForm()
        
        return render(request, 'bento_reservation/reservation.html', {'form': form})

def reservation_success_view(request):
    return render(request, 'bento_reservation/success.html')