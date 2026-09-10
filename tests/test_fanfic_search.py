import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scrapers.search import (
    _buscar_fanfics_plusfiction_direto,
    buscar_fanfics_spirit,
    buscar_fanfics_wattpad,
    buscar_fanfics_plusfiction,
)
from scrapers.search_relevance import filtrar_e_ordenar, normalizar, pontuar_resultado


class Resposta:
    def __init__(self, *, dados=None, texto=""):
        self._dados = dados
        self.text = texto

    def raise_for_status(self):
        pass

    def json(self):
        return self._dados


class RelevanceTests(unittest.TestCase):
    def test_normaliza_acentos_caixa_e_pontuacao(self):
        self.assertEqual(normalizar("  AÇÃO: Proibída! "), "acao proibida")

    def test_exige_todos_os_termos_relevantes(self):
        certo = {"titulo": "Um amor proibido", "autor": "Ana", "url": "https://site/1"}
        aleatorio = {"titulo": "Contrato de amor", "autor": "Ana", "url": "https://site/2"}
        self.assertGreater(pontuar_resultado(certo, "amor proibido"), 0)
        self.assertEqual(pontuar_resultado(aleatorio, "amor proibido"), 0)

    def test_titulo_exato_vem_antes_de_correspondencia_parcial(self):
        resultados = [
            {"titulo": "Entre nós: um amor proibido", "autor": "B", "url": "https://site/1"},
            {"titulo": "Amor proibido", "autor": "A", "url": "https://site/2"},
        ]
        ordenados = filtrar_e_ordenar(resultados, "amor proibido", 10)
        self.assertEqual(ordenados[0]["titulo"], "Amor proibido")

    def test_remove_resultado_claramente_espanhol_ou_ingles(self):
        resultados = [
            {"titulo": "Un amor proibido", "descricao": "Los hijos de una familia tienen una guerra pero ellos se enamoran", "url": "https://site/es"},
            {"titulo": "Amor proibido", "descricao": "Ela não queria amar, mas depois percebe que seu coração não escolhe", "url": "https://site/pt"},
            {"titulo": "Amor proibido", "descricao": "The story of a girl and the boy that was with her before they left", "url": "https://site/en"},
        ]
        ordenados = filtrar_e_ordenar(resultados, "amor proibido", 10)
        self.assertEqual([item["url"] for item in ordenados], ["https://site/pt"])

    def test_texto_curto_com_idioma_incerto_nao_e_descartado(self):
        item = {"titulo": "Amor proibido", "descricao": "Romance", "url": "https://site/1"}
        self.assertEqual(filtrar_e_ordenar([item], "amor proibido", 10), [item])


class SourceFilteringTests(unittest.TestCase):
    @patch("scrapers.search.requests.get")
    def test_wattpad_pede_amostra_maior_filtra_e_limita(self, get):
        get.return_value = Resposta(dados={"stories": [
            {"title": "Resultado aleatório", "description": "texto", "url": "/story/1", "user": {"name": "A"}},
            {"title": "Amor proibido", "description": "Ela não sabe como, mas seu amor não tem fim", "url": "/story/2", "user": {"name": "B"}},
            {"title": "Amor proibido", "description": "The story of a boy and the girl that was with him", "url": "/story/3", "user": {"name": "C"}},
        ]})
        resultados = buscar_fanfics_wattpad("amor proibido", limite=1)
        self.assertEqual([item["autor"] for item in resultados], ["B"])
        self.assertEqual(get.call_args.kwargs["params"]["limit"], 30)

    @patch("scrapers.search.requests.get")
    def test_spirit_nao_aceita_primeiros_artigos_aleatorios(self, get):
        get.return_value = Resposta(texto='''
            <article><h2><a href="/historia/qualquer-1">Uma história qualquer</a></h2><a class="usuario">A</a></article>
            <article><h2><a href="/historia/amor-proibido-2">Amor proibido</a></h2><a class="usuario">B</a></article>''')
        resultados = buscar_fanfics_spirit("amor proibido")
        self.assertEqual([item["autor"] for item in resultados], ["B"])

    @patch("scrapers.search.requests.get")
    def test_plusfiction_remove_menu_ranking_e_recomendacoes(self, get):
        get.return_value = Resposta(texto='''
            <a href="/book/ranking/daily">Livros</a>
            <a href="/book/Contrato-de-Amor-1">Contrato de Amor</a>
            <a href="/book/Amor-Proibido-2">Amor Proibido</a>''')
        resultados = _buscar_fanfics_plusfiction_direto("amor proibido", 10)
        self.assertEqual([item["titulo"] for item in resultados], ["Amor Proibido"])

    @patch("scrapers.search._buscar_fanfics_plusfiction_via_duckduckgo")
    @patch("scrapers.search._buscar_fanfics_plusfiction_direto", return_value=[])
    def test_plusfiction_tenta_fallback_quando_pagina_nao_tem_resultado_relevante(self, direto, fallback):
        fallback.return_value = [{"titulo": "Amor proibido"}]
        self.assertEqual(buscar_fanfics_plusfiction("amor proibido"), fallback.return_value)
        fallback.assert_called_once_with("amor proibido", 10)
