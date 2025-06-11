from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import TIs
from django.contrib import messages
from .forms import TIsForm

# Create your views here.

@login_required
def home(request):
    terras_indigenas = TIs.objects.all().order_by('nome')
    return render(request, 'dominial/home.html', {'terras_indigenas': terras_indigenas})

@login_required
def tis_form(request):
    if request.method == 'POST':
        form = TIsForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Terra Indígena cadastrada com sucesso!')
                return redirect('home')
            except Exception as e:
                messages.error(request, f'Erro ao cadastrar Terra Indígena: {str(e)}')
    else:
        form = TIsForm()
    
    return render(request, 'dominial/tis_form.html', {'form': form})
