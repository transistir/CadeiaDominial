from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from .models import Imovel
# Create your views here.

@login_required
def home(request):
    return render(request, 'dominial/home.html')

def imoveis(request):
    imoveis = Imovel.objects.all() #.order_by('-data_cadastro')[:5] 
    return render(request, 'dominial/imoveis.html', {'imoveis': imoveis})