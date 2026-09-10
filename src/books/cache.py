"""Cache curto em memória para evitar repetir consultas idênticas."""
from functools import wraps
from threading import Lock
from time import monotonic
from weakref import WeakKeyDictionary

from books.models import PaginaLivros


def cachear_paginas(ttl=120):
    dados = WeakKeyDictionary()
    lock = Lock()

    def decorar(funcao):
        @wraps(funcao)
        def executar(instancia, *args, **kwargs):
            chave = (args, tuple(sorted(kwargs.items())))
            agora = monotonic()
            with lock:
                entrada = dados.setdefault(instancia, {}).get(chave)
                if entrada and agora - entrada[0] < ttl:
                    pagina = entrada[1]
                    return PaginaLivros(list(pagina.livros), pagina.tem_proxima, pagina.aviso)
            pagina = funcao(instancia, *args, **kwargs)
            with lock:
                dados.setdefault(instancia, {})[chave] = (monotonic(), pagina)
            return pagina
        return executar
    return decorar
