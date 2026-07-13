from django.db import models


class AlteracoesTipo(models.Model):
    id = models.AutoField(primary_key=True)
    TIPO_CHOICES = [
        ('registro', 'Registro'),
        ('averbacao', 'Averbação'),
        ('nao_classificado', 'Não Classificado')
    ]
    tipo = models.CharField(max_length=50, choices=TIPO_CHOICES)

    def __str__(self):
        return self.tipo


class RegistroTipo(models.Model):
    id = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=100)

    def __str__(self):
        return self.tipo


class AverbacoesTipo(models.Model):
    id = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=100)

    def __str__(self):
        return self.tipo


class Alteracoes(models.Model):
    id = models.AutoField(primary_key=True)
    imovel_id = models.ForeignKey('Imovel', on_delete=models.CASCADE) # Verificar qual atributo usar para o relacionamento com Imóvel
    tipo_alteracao_id = models.ForeignKey(AlteracoesTipo, on_delete=models.CASCADE) # Verificar 'on_delete'
    livro = models.CharField(max_length=50, null=True, blank=True)
    folha = models.CharField(max_length=50, null=True, blank=True)
    cartorio = models.ForeignKey('Cartorios', on_delete=models.CASCADE) # Verificar 'on_delete'
    data_alteracao = models.DateField(null=True, blank=True) # Opcional, para data da alteração a ser registrada
    registro_tipo = models.ForeignKey(RegistroTipo, on_delete=models.CASCADE, null=True, blank=True) # Opcional, para tipo de registro
    averbacao_tipo = models.ForeignKey(AverbacoesTipo, on_delete=models.CASCADE, null=True, blank=True) # Opcional, para tipo de averbação
    titulo = models.CharField(max_length=255, null=True, blank=True) # Opcional, para título do registro ou averbação
    cartorio_origem = models.ForeignKey('Cartorios', on_delete=models.CASCADE, related_name='cartorio_responsavel') # Cartório responsável pela alteração
    livro_origem = models.CharField(max_length=50, null=True, blank=True) # Opcional, para livro de alteração de registro original
    folha_origem = models.CharField(max_length=50, null=True, blank=True) # Opcional, para folha de alteração de registro original
    data_origem = models.DateField(null=True, blank=True) # Opcional, para data de registro original
    transmitente = models.ForeignKey('Pessoas', on_delete=models.CASCADE, related_name='transmitente', null=True, blank=True) # Opcional, para pessoa que transmite o imóvel
    adquirente = models.ForeignKey('Pessoas', on_delete=models.CASCADE, related_name='adquirente', null=True, blank=True) # Opcional, para pessoa que adquire o imóvel
    valor_transacao = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True) # Opcional, para valor da transação
    area = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True) # Opcional, para área do imóvel
    observacoes = models.TextField(null=True, blank=True) # Opcional, para observações adicionais
    data_cadastro = models.DateField(auto_now_add=True) # Data de cadastro da alteração

    class Meta:
        verbose_name = "Alteração"
        verbose_name_plural = "Alterações"

    def __str__(self):
        return f"{self.imovel_id} - {self.tipo_alteracao_id} - {self.data_alteracao}" if self.data_alteracao else f"{self.imovel_id} - {self.tipo_alteracao_id}" 