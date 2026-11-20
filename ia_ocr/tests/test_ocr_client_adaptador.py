"""``AdaptadorComPrazoProxyTests`` — migração VERBATIM de
``ia_ocr/tests/test_ocr_client.py`` (Etapa 13 do plano de 400 linhas).
"""

from types import SimpleNamespace
from unittest.mock import patch

from urllib3.connectionpool import HTTPConnectionPool

from ia_ocr.ocr_client import (
    _AdaptadorComPrazo,
    _PoolHttpComPrazo,
    _PoolHttpsComPrazo,
)


class AdaptadorComPrazoProxyTestsParte:
    def test_proxy_http_usa_classes_de_pool_com_prazo(self):
        gerenciador = _AdaptadorComPrazo().proxy_manager_for('http://127.0.0.1:1')

        self.assertIs(
            gerenciador.pool_classes_by_scheme['http'], _PoolHttpComPrazo
        )
        self.assertIs(
            gerenciador.pool_classes_by_scheme['https'], _PoolHttpsComPrazo
        )

    def test_proxy_socks_mantem_classes_de_pool_proprias(self):
        class PoolSocks(HTTPConnectionPool):
            pass

        gerenciador_socks = SimpleNamespace(
            pool_classes_by_scheme={'http': PoolSocks, 'https': PoolSocks}
        )
        with patch(
            'requests.adapters.HTTPAdapter.proxy_manager_for',
            return_value=gerenciador_socks,
        ):
            resultado = _AdaptadorComPrazo().proxy_manager_for(
                'socks5h://127.0.0.1:1080'
            )

        self.assertEqual(
            resultado.pool_classes_by_scheme, {'http': PoolSocks, 'https': PoolSocks}
        )
