from django.db import models


class Pessoas(models.Model):
    id = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=100)
    cpf = models.CharField(max_length=11, unique=True, null=True, blank=True) # Verificar formato (Cadastro de Pessoa Física - CPF)
    rg = models.CharField(max_length=20, null=True, blank=True) # Opcional, Registro Geral
    data_nascimento = models.DateField(null=True, blank=True) # Opcional, para data de nascimento
    email = models.EmailField(null=True, blank=True) # Opcional, para email
    telefone = models.CharField(max_length=15, null=True, blank=True) # Opcional, para telefone

    class Meta:
        verbose_name = "Pessoa"
        verbose_name_plural = "Pessoas"
    
    def __str__(self):
        return self.nome 