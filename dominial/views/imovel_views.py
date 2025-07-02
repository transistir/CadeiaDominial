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
        cartorio_id = request.POST.get('cartorio_id')
        if cartorio_id:
            try:
                cartorio = Cartorios.objects.get(pk=cartorio_id)
                form.instance.cartorio = cartorio
            except Cartorios.DoesNotExist:
                pass
        if form.is_valid():
            imovel = form.save(commit=False)
            imovel.terra_indigena_id = tis
            proprietario_id = form.cleaned_data.get('proprietario')
            nome = form.cleaned_data.get('proprietario_nome')
            if proprietario_id:
                try:
                    imovel.proprietario = Pessoas.objects.get(id=proprietario_id)
                except Pessoas.DoesNotExist:
                    messages.error(request, 'O proprietário selecionado não foi encontrado.')
                    return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})
            else:
                cpf = request.POST.get('cpf')
                rg = request.POST.get('rg')
                data_nascimento = request.POST.get('data_nascimento')
                email = request.POST.get('email')
                telefone = request.POST.get('telefone')
                if nome and cpf:
                    nova_pessoa = Pessoas.objects.create(
                        nome=nome,
                        cpf=cpf,
                        rg=rg,
                        email=email,
                        telefone=telefone,
                        data_nascimento=data_nascimento if data_nascimento else None
                    )
                    imovel.proprietario = nova_pessoa
                else:
                    messages.error(request, "Para cadastrar novo proprietário, preencha pelo menos Nome e CPF.")
                    return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})
            imovel.save()
            messages.success(request, 'Imóvel cadastrado com sucesso!')
            return redirect('tis_detail', tis_id=tis_id)
        else:
            messages.error(request, 'Erro no formulário. Verifique os dados.')
    else:
        form = ImovelForm(instance=imovel)
    return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel}) 