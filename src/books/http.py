"""Cliente HTTP compartilhado, com novas tentativas curtas e limitadas."""
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def criar_cliente():
    cliente = requests.Session()
    tentativas = Retry(
        total=2, connect=2, read=1, backoff_factor=.35,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}), raise_on_status=False,
    )
    cliente.mount("https://", HTTPAdapter(max_retries=tentativas, pool_connections=8,
                                           pool_maxsize=8))
    return cliente
