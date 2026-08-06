from django.db import migrations


CAMPOS_POR_MODELO = {
    "Lancamento": (
        "titulo",
        "forma",
        "descricao",
        "origem",
        "detalhes",
        "observacoes",
        "numero_lancamento",
        "livro_transacao",
        "folha_transacao",
        "livro_origem",
        "folha_origem",
    ),
    "Documento": (
        "origem",
        "observacoes",
        "classificacao_fim_cadeia",
        "sigla_patrimonio_publico",
    ),
    "Imovel": ("observacoes",),
    "Alteracoes": (
        "titulo",
        "observacoes",
        "livro",
        "folha",
        "livro_origem",
        "folha_origem",
    ),
    "FimCadeia": ("descricao", "sigla"),
}


def normalizar_none_textual(apps, schema_editor):
    db_alias = schema_editor.connection.alias

    for model_name, campos in CAMPOS_POR_MODELO.items():
        model = apps.get_model("dominial", model_name)

        for campo in campos:
            # NICE-TO-HAVE N-4: registrar contagem antes de atualizar
            # para que o log de deploy documente o que foi destruído.
            qs = model.objects.using(db_alias).filter(**{campo: "None"})
            count = qs.count()
            if count:
                print(f"  [0056] {model_name}.{campo}: {count} linha(s) afetada(s)")
                qs.update(**{campo: None})


class Migration(migrations.Migration):
    atomic = True

    dependencies = [
        ("dominial", "0055_add_data_presumida_documento"),
    ]

    operations = [
        migrations.RunPython(
            normalizar_none_textual,
            migrations.RunPython.noop,
        ),
    ]
