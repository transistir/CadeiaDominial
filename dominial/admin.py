from django.contrib import admin
from .models import TIs, Cartorios, Pessoas, Imovel, Alteracoes

admin.site.site_header = "Sistema de Cadeia Dominial"
admin.site.site_title = "Administração"
admin.site.index_title = "Painel de Gestão"


# Register your models here.

admin.site.register(TIs)
admin.site.register(Cartorios)
admin.site.register(Pessoas)
admin.site.register(Imovel)
admin.site.register(Alteracoes)
