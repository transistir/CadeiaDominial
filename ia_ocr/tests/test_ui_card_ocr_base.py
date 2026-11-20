"""Infraestrutura compartilhada dos testes do card OCR, migrada verbatim."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.test.html import Element, parse_html
from django.urls import reverse

from .factories import criar_documento_digital


def _atributos(elemento):
    """Dicionário nome → valor dos atributos de um elemento parseado."""
    return dict(elemento.attributes)


def _elementos(conteudo, nome_tag, presentes=(), valores=None):
    """Elementos `nome_tag` que têm todos os atributos em `presentes` e os
    valores de `valores`. A ordem dos atributos no HTML é irrelevante."""
    valores = valores or {}
    achados = []

    def visitar(no):
        if not isinstance(no, Element):
            return
        atributos = _atributos(no)
        if (
            no.name == nome_tag
            and all(nome in atributos for nome in presentes)
            and all(atributos.get(nome) == valor for nome, valor in valores.items())
        ):
            achados.append(no)
        for filho in no.children:
            visitar(filho)

    visitar(parse_html(conteudo))
    return achados


def _texto(elemento):
    """Texto direto de um elemento parseado (filhos str concatenados)."""
    return ''.join(filho for filho in elemento.children if isinstance(filho, str))


def _texto_de_estilos(conteudo):
    """Conteúdo textual de todos os <style> da página."""
    pedacos = []
    for estilo in _elementos(conteudo, 'style'):
        pedacos.extend(filho for filho in estilo.children if isinstance(filho, str))
    return '\n'.join(pedacos)



class CardOcrUploadBase(TestCase):
    """Cenário: dono atribuído à TI do documento, como em test_views_ocr_jobs."""

    @classmethod
    def setUpTestData(cls):
        cls.dono = User.objects.create_user(username='dono-ui', password='senha-dono')
        cls.arquivo = criar_documento_digital(upload_por=cls.dono)
        cls.imovel = cls.arquivo.documento.imovel
        cls.ti = cls.imovel.terra_indigena_id
        cls.documento = cls.arquivo.documento

        from dominial.models import UserTI
        UserTI.objects.create(user=cls.dono, tis=cls.ti)

    def url_upload(self):
        return reverse('upload_documento_digital', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
        })

    def url_criar(self):
        return reverse('criar_job_ocr', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
            'arquivo_id': self.arquivo.pk,
        })

    def pagina(self):
        self.client.force_login(self.dono)
        return self.client.get(self.url_upload())

    def url_texto(self, job):
        return reverse('texto_job_ocr', kwargs={
            'tis_id': self.ti.pk,
            'imovel_id': self.imovel.pk,
            'documento_id': self.documento.pk,
            'job_id': job.job_id,
        })
