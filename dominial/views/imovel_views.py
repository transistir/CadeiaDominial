from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import Imovel, TIs, Pessoas, Cartorios
from ..forms import ImovelForm
from ..services.lancamento_documento_service import LancamentoDocumentoService

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
        
        if form.is_valid():
            imovel = form.save(commit=False)
            imovel.terra_indigena_id = tis
            # Atribuir o cartório explicitamente
            imovel.cartorio = form.cleaned_data.get('cartorio')
            # Processar proprietário
            if nome_proprietario:
                # Truncar nome se for muito longo (máximo 255 caracteres)
                nome_truncado = nome_proprietario[:255] if len(nome_proprietario) > 255 else nome_proprietario
                
                # Avisar se o nome foi truncado
                if len(nome_proprietario) > 255:
                    messages.warning(request, f'O nome do proprietário foi truncado para {len(nome_truncado)} caracteres.')
                
                # Criar ou buscar proprietário
                # Primeiro verificar se já existe uma pessoa com este nome
                pessoas_existentes = Pessoas.objects.filter(nome=nome_truncado)
                
                if pessoas_existentes.exists():
                    # Se existem múltiplas pessoas com o mesmo nome, usar a primeira
                    if pessoas_existentes.count() > 1:
                        messages.warning(request, f'Encontradas {pessoas_existentes.count()} pessoas com o nome "{nome_truncado}". Usando a primeira encontrada.')
                    proprietario = pessoas_existentes.first()
                    created = False
                else:
                    # Criar nova pessoa
                    proprietario = Pessoas.objects.create(
                        nome=nome_truncado,
                        cpf=None,  # CPF é opcional, usar None em vez de string vazia
                        rg='',
                        email='',
                        telefone=''
                    )
                    created = True
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
                
                # Criar automaticamente o documento de matrícula para o imóvel
                if not imovel_id:  # Apenas para novos imóveis
                    try:
                        documento_matricula = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
                        messages.info(request, f'Documento de matrícula "{documento_matricula.numero}" criado automaticamente.')
                    except Exception as e:
                        messages.warning(request, f'Imóvel criado, mas houve um problema ao criar o documento de matrícula: {str(e)}')
                
                messages.success(request, 'Imóvel cadastrado com sucesso!')
                return redirect('tis_detail', tis_id=tis_id)
            except Exception as e:
                messages.error(request, f'Erro ao salvar imóvel: {str(e)}')
                return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})
        else:
            # Exibir erros específicos do formulário
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
            if not form.errors:
                messages.error(request, 'Erro no formulário. Verifique os dados.')
    else:
        form = ImovelForm(instance=imovel)
    
    return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel}) 