from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class UserTI(models.Model):
    """Atribuição de uma TI inteira a um usuário: cobre os imóveis atuais e futuros."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tis_atribuidas',
        verbose_name='Usuário',
    )
    tis = models.ForeignKey(
        'TIs',
        on_delete=models.CASCADE,
        related_name='usuarios_ti',
        verbose_name='Terra Indígena',
    )
    data_atribuicao = models.DateTimeField(auto_now_add=True)
    atribuido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='atribuicoes_ti_feitas',
    )

    class Meta:
        unique_together = ('user', 'tis')
        indexes = [models.Index(fields=['tis'], name='dom_userti_tis_idx')]
        verbose_name = 'Atribuição de TI'
        verbose_name_plural = 'Atribuições de TI'
        ordering = ['user__username', 'tis__nome']

    def __str__(self):
        return f'{self.user} → {self.tis}'


class GroupTI(models.Model):
    """Atribuição de uma TI a uma equipe: todo membro herda, entra e sai na hora."""

    group = models.ForeignKey(
        'auth.Group',
        on_delete=models.CASCADE,
        related_name='tis_atribuidas',
        verbose_name='Equipe',
    )
    tis = models.ForeignKey('TIs', on_delete=models.CASCADE, related_name='grupos_ti')
    data_atribuicao = models.DateTimeField(auto_now_add=True)
    atribuido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='atribuicoes_grupo_feitas',
    )

    class Meta:
        unique_together = ('group', 'tis')
        indexes = [models.Index(fields=['tis'], name='dom_groupti_tis_idx')]

    def clean(self):
        super().clean()
        if not self.group_id:
            return
        try:
            acesso = self.group.acesso
        except GrupoAcesso.DoesNotExist:
            acesso = None
        if acesso is None or acesso.tipo != GrupoAcesso.EQUIPE:
            raise ValidationError('TIs só podem ser atribuídas a equipes, não a perfis.')

    def __str__(self):
        return f'{self.group} → {self.tis}'


class GrupoAcesso(models.Model):
    """Metadados do auth.Group: é um perfil (permissões) ou uma equipe (TIs)?"""

    PERFIL = 'perfil'
    EQUIPE = 'equipe'
    TIPOS = [(PERFIL, 'Perfil'), (EQUIPE, 'Equipe')]

    group = models.OneToOneField(
        'auth.Group',
        on_delete=models.CASCADE,
        related_name='acesso',
    )
    tipo = models.CharField(max_length=10, choices=TIPOS)
    protegido = models.BooleanField(default=False)
    descricao = models.CharField(max_length=255, blank=True)
    acesso_todas_tis = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name='Acesso a todas as TIs',
        help_text=(
            'Equipe "global": todo membro passa a ver todas as TIs — as atuais e '
            'as cadastradas no futuro — e todos os imóveis dessas TIs. É uma '
            'propriedade calculada dinamicamente pelo manager de segregação, não '
            'gera linhas em GroupTI e não precisa de sincronização quando uma TI '
            'nova é criada. Só é válido para equipes (tipo=EQUIPE); perfis nunca '
            'podem ativá-lo.'
        ),
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(acesso_todas_tis=False) | Q(tipo='equipe'),
                name='grupoacesso_global_so_equipe',
                violation_error_message=(
                    'Acesso a todas as TIs só pode ser ativado para equipes, não para perfis.'
                ),
            ),
        ]

    def clean(self):
        super().clean()
        if self.acesso_todas_tis and self.tipo != self.EQUIPE:
            raise ValidationError(
                {'acesso_todas_tis': 'Acesso a todas as TIs só pode ser ativado para equipes, não para perfis.'}
            )

    def __str__(self):
        return str(self.group)
