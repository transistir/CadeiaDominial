from django.db import models


class TIs(models.Model):
    id = models.AutoField(primary_key=True)
    terra_referencia = models.ForeignKey('TerraIndigenaReferencia', on_delete=models.PROTECT, null=True, blank=True)
    nome = models.CharField(max_length=100)
    codigo = models.CharField(max_length=50, unique=True)
    etnia = models.CharField(max_length=50)
    estado = models.CharField(max_length=100, null=True, blank=True, help_text="Estados separados por vírgula (ex: AM, PA, MT)")
    area = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Área em hectares")
    data_cadastro = models.DateField(auto_now_add=True)
    
    class Meta:
        verbose_name = "TI"
        verbose_name_plural = "TIs"

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        if self.terra_referencia:
            self.nome = self.terra_referencia.nome
            self.codigo = self.terra_referencia.codigo
            self.etnia = self.terra_referencia.etnia
            self.estado = self.terra_referencia.estado
            self.area = self.terra_referencia.area_ha
        super().save(*args, **kwargs)


class TerraIndigenaReferencia(models.Model):
    codigo = models.CharField(max_length=50, unique=True)
    nome = models.CharField(max_length=255)
    etnia = models.CharField(max_length=255, blank=True, null=True)
    estado = models.CharField(max_length=2, blank=True, null=True)
    municipio = models.CharField(max_length=255, blank=True, null=True)
    area_ha = models.FloatField(blank=True, null=True)
    fase = models.CharField(max_length=100, blank=True, null=True)
    modalidade = models.CharField(max_length=100, blank=True, null=True)
    coordenacao_regional = models.CharField(max_length=100, blank=True, null=True)
    data_regularizada = models.DateField(blank=True, null=True)
    data_homologada = models.DateField(blank=True, null=True)
    data_declarada = models.DateField(blank=True, null=True)
    data_delimitada = models.DateField(blank=True, null=True)
    data_em_estudo = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nome} ({self.codigo})"

    class Meta:
        verbose_name = "Terra Indígena (Referência)"
        verbose_name_plural = "Terras Indígenas (Referência)"
        ordering = ['nome']


class TIs_Imovel(models.Model):
    tis_codigo = models.ForeignKey(TIs, on_delete=models.CASCADE, related_name='tis_codigo')
    imovel = models.ForeignKey('Imovel', on_delete=models.CASCADE, related_name='imovel')
    
    def __str__(self):
        return self.tis_codigo.nome + " - " + self.imovel.nome 