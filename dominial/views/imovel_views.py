from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import Imovel, TIs, Pessoas, Cartorios
from ..forms import ImovelForm

@login_required
def imovel_form(request, tis_id, imovel_id=None):
    tis = get_object_or_404(TIs, pk=tis_id)
    imovel = None
    if imovel_id:
        imovel = get_object_or_404(Imovel, pk=imovel_id)
    
    if request.method == 'POST':
        form = ImovelForm(request.POST, instance=imovel)
        
        # Obter dados do formulário
        nome_proprietario = request.POST.get('proprietario_nome')
        
        # Debug: verificar dados do POST
        print("DEBUG: Dados do POST:")
        print("proprietario_nome:", nome_proprietario)
        print("cartorio:", request.POST.get('cartorio'))
        print("Todos os dados:", dict(request.POST))
        
        if form.is_valid():
            imovel = form.save(commit=False)
            imovel.terra_indigena_id = tis
            
            # Debug: verificar dados do form
            print("DEBUG: Dados do form:")
            print("cartorio do form:", imovel.cartorio)
            print("form.cleaned_data:", form.cleaned_data)
            
            # Atribuir o cartório explicitamente
            imovel.cartorio = form.cleaned_data.get('cartorio')
            print("DEBUG: Cartório após atribuição:", imovel.cartorio)
            
            # Processar proprietário
            if nome_proprietario:
                # Criar ou buscar proprietário
                proprietario, created = Pessoas.objects.get_or_create(
                    nome=nome_proprietario,
                    defaults={
                        'nome': nome_proprietario,
                        'cpf': '',  # Campo obrigatório, mas não temos no formulário simplificado
                        'rg': '',
                        'email': '',
                        'telefone': ''
                    }
                )
                imovel.proprietario = proprietario
            else:
                messages.error(request, 'Nome do proprietário é obrigatório.')
                return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})
            
            # O cartório já foi processado pelo form.is_valid() e está em imovel.cartorio
            if not imovel.cartorio:
                messages.error(request, 'Seleção de cartório é obrigatória.')
                return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})
            
            # Salvar imóvel
            try:
                imovel.save()
                messages.success(request, 'Imóvel cadastrado com sucesso!')
                return redirect('tis_detail', tis_id=tis_id)
            except Exception as e:
                messages.error(request, f'Erro ao salvar imóvel: {str(e)}')
                return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})
        else:
            messages.error(request, 'Erro no formulário. Verifique os dados.')
            print("Erros do formulário:", form.errors)
    else:
        form = ImovelForm(instance=imovel)
    
    return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel}) 