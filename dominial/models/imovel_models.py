from django.db import models
from django.core.exceptions import ValidationError

from .identidade_expressions import numero_documento_normalizado_expression


class Imovel(models.Model):
    """
    Modelo de Imóvel.
    
    IMPORTANTE: A matrícula deve ser única por cartório, não globalmente.
    Isso permite que diferentes cartórios tenham imóveis com a mesma matrícula,
    o que é o comportamento correto no sistema de registro de imóveis brasileiro.
    """
    TIPO_DOCUMENTO_CHOICES = [
        ('matricula', 'Matrícula'),
        ('transcricao', 'Transcrição'),
    ]
    
    id = models.AutoField(primary_key=True)
    terra_indigena_id = models.ForeignKey('TIs', on_delete=models.PROTECT) 
    nome = models.CharField(max_length=100) # Obrigatório?
    proprietario = models.ForeignKey('Pessoas', on_delete=models.PROTECT) # Verificar 'on_delete'
    # Removido unique=True - a unicidade é garantida pela constraint (matricula, cartorio)
    matricula = models.CharField(max_length=50, help_text="Número da matrícula. Deve ser único por cartório.")
    matricula_normalizada = models.GeneratedField(
        expression=numero_documento_normalizado_expression('matricula'),
        output_field=models.CharField(max_length=50),
        db_persist=True,
        editable=False,
    )
    tipo_documento_principal = models.CharField(
        max_length=20,
        choices=TIPO_DOCUMENTO_CHOICES,
        default='matricula',
        verbose_name='Tipo do Documento Principal'
    )
    observacoes = models.TextField(null=True, blank=True) # Opcional, para observações adicionais
    cartorio = models.ForeignKey(
        'Cartorios',
        on_delete=models.PROTECT,
        help_text='Cartório obrigatório da identidade registral do imóvel.',
    )
    data_cadastro = models.DateField(auto_now_add=True) # Data de cadastro do imóvel
    arquivado = models.BooleanField(default=False, verbose_name="Arquivado") # Campo para arquivar imóveis

    class Meta:
        verbose_name = "Imóvel"
        verbose_name_plural = "Imóveis"
        # Constraint única: identidade registral completa (tipo + matrícula + cartório)
        constraints = [
            models.UniqueConstraint(
                fields=['tipo_documento_principal', 'matricula_normalizada', 'cartorio'],
                name='unique_imovel_identidade_registral',
            ),
        ]
        # Índice para melhorar performance de buscas
        indexes = [
            models.Index(fields=['matricula', 'cartorio'], name='dom_imovel_mat_cart_idx'),
        ]

    def __str__(self):
        return self.matricula

    def clean(self):
        if self.pk is None and not self.cartorio_id:
            raise ValidationError('Cartório é obrigatório para identificar o imóvel.')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def get_sigla_formatada(self):
        """
        Retorna a sigla formatada baseada no tipo do documento
        M + número para matrícula, T + número para transcrição
        """
        if self.tipo_documento_principal == 'matricula':
            return f"M{self.matricula}"
        elif self.tipo_documento_principal == 'transcricao':
            return f"T{self.matricula}"
        else:
            return self.matricula


class Cartorios(models.Model):
    TIPO_CHOICES = [
        ('CRI', 'Cartório de Registro de Imóveis'),
        ('OUTRO', 'Outro'),
    ]
    
    nome = models.CharField(max_length=200)
    # cns: UNIQUE vira PARCIAL `WHERE deleted_at IS NULL` (migration 0055).
    # UniqueConstraint permite reativar cartório soft-deletado sem colidir CNS.
    cns = models.CharField(
        max_length=20,
        help_text='CNS — código CNJ. UNIQUE apenas entre cartórios ativos.',
    )
    endereco = models.CharField(max_length=200, null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    estado = models.CharField(max_length=2, null=True, blank=True)
    cidade = models.CharField(max_length=100, null=True, blank=True)
    tipo = models.CharField(
        max_length=10,
        choices=TIPO_CHOICES,
        default='CRI',
        verbose_name='Tipo de Cartório'
    )
    # Soft-delete LGPD (AGENTS.md Q2=B). NULL = ativo.
    deleted_at = models.DateTimeField(
        blank=True,
        null=True,
        default=None,
        db_index=True,
        help_text='Soft-delete LGPD. NULL = ativo. Conforme AGENTS.md Q2=B.',
        verbose_name='Soft-delete',
    )

    def __str__(self):
        return f"{self.nome} - {self.cidade}/{self.estado}" if self.cidade and self.estado else self.nome

    class Meta:
        verbose_name = 'Cartório'
        verbose_name_plural = 'Cartórios'
        ordering = ['tipo', 'estado', 'cidade', 'nome']
        constraints = [
            models.UniqueConstraint(
                fields=['cns'],
                condition=models.Q(deleted_at__isnull=True),
                name='cartorio_cns_ativo_unique',
            ),
        ]
        indexes = [
            models.Index(
                fields=['deleted_at'],
                condition=models.Q(deleted_at__isnull=True),
                name='cartorio_ativo_idx',
            ),
        ]


class CartorioMergeLog(models.Model):
    """Auditoria irreversível de merges de cartórios (issue #110).

    Cada linha é um merge (re)executado. PK auto-incrementa, sem UNIQUE
    — múltiplos merges do mesmo par (rollback + re-apply) são permitidos.
    Usado por `--rollback-fase N` do command `resolver_cartorios_fantasmas`.
    """
    ghost_id = models.IntegerField(
        help_text='ID do cartório soft-deletado (source do merge)',
    )
    target_id = models.IntegerField(
        help_text='ID do cartório que recebeu os vínculos',
    )
    fase = models.IntegerField(
        help_text='Fase do plano: 1 (órfãos), 2 (secundários), 3 (críticos)',
    )
    fk_breakdown_json = models.JSONField(
        help_text='Contagem de FKs reatribuídas por modelo/campo',
    )
    decisao_csv_sha256 = models.CharField(
        max_length=64,
        help_text='SHA-256 do decisao.csv usado',
    )
    applied_at = models.DateTimeField(auto_now_add=True)
    applied_by = models.CharField(
        max_length=200,
        help_text='Usuário que executou o command (getpass.getuser())',
    )
    git_commit = models.CharField(
        max_length=40,
        blank=True,
        default='',
        help_text='SHA do commit no momento do apply',
    )
    status = models.CharField(
        max_length=20,
        default='SUCCESS',
        help_text='SUCCESS | SKIPPED_CONFLICT | ERROR',
    )
    detalhes_json = models.JSONField(
        blank=True,
        null=True,
        help_text='Detalhes extras (conflitos, warnings, etc.)',
    )

    class Meta:
        verbose_name = 'Log de Merge de Cartórios'
        verbose_name_plural = 'Logs de Merge de Cartórios'
        ordering = ['-applied_at']


class ImportacaoCartorios(models.Model):
    estado = models.CharField(max_length=2)
    data_inicio = models.DateTimeField(auto_now_add=True)
    data_fim = models.DateTimeField(null=True, blank=True)
    total_cartorios = models.IntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=[
            ('pendente', 'Pendente'),
            ('em_andamento', 'Em Andamento'),
            ('concluido', 'Concluído'),
            ('erro', 'Erro'),
        ],
        default='pendente'
    )
    erro = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Importação de Cartórios'
        verbose_name_plural = 'Importações de Cartórios'
        ordering = ['-data_inicio']

    def __str__(self):
        return f"Importação {self.estado} - {self.status}"
