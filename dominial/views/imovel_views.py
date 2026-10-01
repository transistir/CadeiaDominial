import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..managers import usuario_tem_ti_inteira
from ..models import Imovel, TIs, Pessoas, Cartorios
from ..forms import ImovelForm
from ..services.imovel_documento_service import ImovelDocumentoService
from ..services.lancamento_documento_service import LancamentoDocumentoService

logger = logging.getLogger(__name__)

@login_required
def imovel_form(request, tis_id, imovel_id=None):
    if not usuario_tem_ti_inteira(request.user, tis_id):
        raise Http404
    tis = get_object_or_404(TIs, pk=tis_id)
    imovel = None
    if imovel_id:
        imovel = get_object_or_404(
            Imovel.objects.for_user(request.user),
            pk=imovel_id,
            terra_indigena_id=tis,
        )
    
    if request.method == 'POST':
        form = ImovelForm(request.POST, instance=imovel, user=request.user)
        
        # Obter dados do formulário
        nome_proprietario = request.POST.get('proprietario_nome')
        
        if form.is_valid():
            imovel = form.save(commit=False)
            imovel.terra_indigena_id = tis
            # Atribuir o cartório explicitamente
            imovel.cartorio = form.cleaned_data.get('cartorio')
            if not nome_proprietario:
                messages.error(request, 'Nome do proprietário é obrigatório.')
                return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})

            # Truncar nome se for muito longo (máximo 255 caracteres)
            nome_truncado = nome_proprietario[:255]
            if len(nome_proprietario) > 255:
                messages.warning(request, f'O nome do proprietário foi truncado para {len(nome_truncado)} caracteres.')
            
            # O cartório já foi processado pelo form.is_valid() e está em imovel.cartorio
            if not imovel.cartorio:
                messages.error(request, 'Seleção de cartório é obrigatória.')
                return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})
            
            # Salvar imóvel (e sincronizar cartório do documento principal, #210)
            try:
                with transaction.atomic():
                    # Resolver/criar o proprietário na mesma transação do imóvel
                    # evita deixar Pessoas órfãs em falhas posteriores.
                    pessoas_existentes = Pessoas.objects.filter(nome=nome_truncado)
                    quantidade_pessoas = pessoas_existentes.count()
                    if quantidade_pessoas:
                        if quantidade_pessoas > 1:
                            messages.warning(request, f'Encontradas {quantidade_pessoas} pessoas com o nome "{nome_truncado}". Usando a primeira encontrada.')
                        proprietario = pessoas_existentes.first()
                    else:
                        proprietario = Pessoas.objects.create(
                            nome=nome_truncado,
                            cpf=None,
                            rg='',
                            email='',
                            telefone='',
                        )
                    imovel.proprietario = proprietario
                    imovel.save()
                    
                    # Sincronizar cartório do documento principal (#210)
                    aviso_sincronizacao = None
                    if getattr(form, 'cartorio_mudou', False):
                        aviso_sincronizacao = (
                            ImovelDocumentoService.sincronizar_cartorio_documento_principal(
                                imovel, user=request.user
                            )
                        )
                    
                    # Criar automaticamente o documento principal para o imóvel (#230)
                    if not imovel_id:  # Apenas para novos imóveis
                        documento_principal = LancamentoDocumentoService.criar_documento_matricula_automatico(imovel)
                
                # Mensagens após o commit
                if not imovel_id:
                    rotulo = documento_principal.tipo.get_tipo_display().lower()
                    messages.info(
                        request,
                        f'Documento de {rotulo} "{documento_principal.numero}" criado automaticamente.',
                    )
                
                if aviso_sincronizacao:
                    messages.warning(request, aviso_sincronizacao)
                
                messages.success(request, 'Imóvel cadastrado com sucesso!')
                return redirect('tis_detail', tis_id=tis_id)
            except ValidationError as e:
                messages.error(request, '; '.join(e.messages))
                return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})
            except Exception:
                logger.exception('Erro ao salvar imóvel tis=%s imovel=%s', tis_id, imovel_id)
                messages.error(request, 'Erro ao salvar imóvel.')
                return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})
        else:
            # Exibir erros específicos do formulário
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
            if not form.errors:
                messages.error(request, 'Erro no formulário. Verifique os dados.')
    else:
        form = ImovelForm(instance=imovel, user=request.user)
    
    return render(request, 'dominial/imovel_form.html', {'form': form, 'tis': tis, 'imovel': imovel})
