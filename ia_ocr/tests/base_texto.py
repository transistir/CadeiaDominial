"""Base compartilhada dos testes da tela de confirmação do texto (issue #261)."""

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from dominial.models import UserTI

from .factories import criar_documento_digital, criar_job_concluido

TEXTOS = [
    'Texto sintético da página 1',
    'Texto sintético da página 2',
    'Texto sintético da página 3',
]


def _texto_completo(no):
    """Todo o texto de um nó parseado, descendentes incluídos."""
    if isinstance(no, str):
        return no
    return ' '.join(_texto_completo(filho) for filho in no.children)


class TelaTextoBase(TestCase):
    """Cenário: dono atribuído à TI do documento, intruso sem atribuição."""

    @classmethod
    def setUpTestData(cls):
        cls.dono = User.objects.create_user(username='dono-texto', password='senha-dono')
        cls.sem_acesso = User.objects.create_user(username='zeca-texto', password='senha-zeca')

        cls.arquivo = criar_documento_digital(upload_por=cls.dono)
        cls.documento = cls.arquivo.documento
        cls.imovel = cls.documento.imovel
        cls.ti = cls.imovel.terra_indigena_id
        UserTI.objects.create(user=cls.dono, tis=cls.ti)

    def setUp(self):
        self.job = criar_job_concluido(self.arquivo, textos=TEXTOS)

    def kwargs_url(self, job=None, **extra):
        job = job or self.job
        return {
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
            'job_id': job.job_id,
            **extra,
        }

    def url(self, nome, job=None, **extra):
        return reverse(nome, kwargs=self.kwargs_url(job, **extra))

    def url_tela(self, pagina=None, job=None):
        base = self.url('texto_job_ocr', job)
        return f'{base}?pagina={pagina}' if pagina else base

    def url_pdf(self):
        return reverse('servir_documento_digital', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
            'arquivo_id': self.arquivo.pk,
        })

    def url_upload(self):
        return reverse('upload_documento_digital', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
        })

    def pagina(self, numero, job=None):
        return (job or self.job).paginas.get(numero_pagina=numero)

    def versao(self, numero, job=None):
        """Versão atual da página: a que o formulário da tela enviaria."""
        return self.pagina(numero, job).versao

    def mensagens(self, resposta):
        return [(m.level_tag, str(m)) for m in get_messages(resposta.wsgi_request)]
