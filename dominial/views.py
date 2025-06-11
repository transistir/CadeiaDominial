from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from .models import Imovel, TIs, Cartorios, Pessoas, Alteracoes
# Create your views here.

@login_required
def home(request):
    return render(request, 'dominial/home.html')

def imoveis(request):
    imoveis = Imovel.objects.all() #.order_by('-data_cadastro')[:5] 
    return render(request, 'dominial/imoveis.html', {'imoveis': imoveis})

def tis(request):
    tis = TIs.objects.all() #.order_by('-data_cadastro')[:5] 
    return render(request, 'dominial/tis.html', {'tis': tis})

def cartorios(request):
    cartorios = Cartorios.objects.all() #.order_by('-data_cadastro')[:5] 
    return render(request, 'dominial/cartorios.html', {'cartorios': cartorios})

def pessoas(request):
    pessoas = Pessoas.objects.all() #.order_by('-data_cadastro')[:5] 
    return render(request, 'dominial/pessoas.html', {'pessoas': pessoas})

def alteracoes(request):
    alteracoes = Alteracoes.objects.all() #.order_by('-data_cadastro')[:5] 
    return render(request, 'dominial/alteracoes.html', {'alteracoes': alteracoes})