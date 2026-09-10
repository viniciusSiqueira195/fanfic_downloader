import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from converters.filenames import nome_seguro
from converters.normalizacao import normalizar
from converters.to_epub import salvar_epub
from converters.to_txt import salvar_txt
from scrapers.chapter_selection import interpretar_selecao, selecionar_capitulos, SelecaoCapitulosError
from updater import (_copy_update_tree, _extrair_zip_seguro, _is_newer_version,
                     _normalize_sha256)


class CoreTests(unittest.TestCase):
    def test_intervalos_ordenados_sem_repeticao(self):
        self.assertEqual(interpretar_selecao("3, 1-3, 5"), [1, 2, 3, 5])

    def test_selecao_invalida(self):
        for texto in ("", "0", "3-1", "-1", "a", "1,", "1.5"):
            with self.subTest(texto=texto), self.assertRaises(SelecaoCapitulosError):
                interpretar_selecao(texto)

    def test_selecao_preserva_numeracao_original(self):
        self.assertEqual(selecionar_capitulos(["a", "b", "c"], "3,1"), [(1, "a"), (3, "c")])

    def test_capitulo_inexistente(self):
        with self.assertRaises(SelecaoCapitulosError):
            selecionar_capitulos(["a"], "2")

    def test_normalizacao_acessivel_preserva_acentos(self):
        self.assertEqual(normalizar("ᴀʙᴄ Ａ café"), "abc A café")

    def test_nomes_portaveis(self):
        for entrada, esperado in [("CON", "_CON"), ("AUX.txt", "_AUX.txt"),
                                  ("../<>:", "Livro"), ("Ação. ", "Ação"),
                                  ("A/B\\C", "ABC")]:
            with self.subTest(entrada=entrada):
                self.assertEqual(nome_seguro(entrada), esperado)

    def test_nome_longo_limitado(self):
        self.assertLessEqual(len(nome_seguro("a" * 300)), 140)

    def test_txt_preserva_texto_e_normaliza_decoracoes(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = salvar_txt("ᴀmor", "Olá, ação & <texto>!", pasta)
            self.assertEqual(Path(caminho).read_text(encoding="utf-8"), "amor\n\nOlá, ação & <texto>!")

    def test_epub_preserva_texto_literal_e_navegacao(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = salvar_epub("ᴀ & <B>", "Olá <script>literal</script> & fim", pasta)
            with zipfile.ZipFile(caminho) as arquivo:
                historia = ET.fromstring(arquivo.read("EPUB/historia.xhtml"))
                texto = "".join(historia.itertext())
                self.assertIn("a & <B>", texto)
                self.assertIn("Olá <script>literal</script> & fim", texto)
                self.assertFalse(any(e.tag.endswith("script") for e in historia.iter()))
                self.assertIn("EPUB/nav.xhtml", arquivo.namelist())

    def test_epubs_tem_identificadores_distintos(self):
        with tempfile.TemporaryDirectory() as pasta:
            ids = []
            for titulo in ("Livro A", "Livro B"):
                with zipfile.ZipFile(salvar_epub(titulo, "Texto", pasta)) as arquivo:
                    raiz = ET.fromstring(arquivo.read("EPUB/content.opf"))
                    ids.append(raiz.find(".//{http://purl.org/dc/elements/1.1/}identifier").text)
            self.assertNotEqual(*ids)

    def test_versoes_estaveis(self):
        self.assertTrue(_is_newer_version("v1.10", "1.9"))
        self.assertFalse(_is_newer_version("1.0", "1.0.0"))

    def test_hash_invalido_rejeitado(self):
        with self.assertRaises(ValueError):
            _normalize_sha256("abc")
        self.assertEqual(_normalize_sha256("sha256:" + "A" * 64), "a" * 64)

    def test_atualizador_rejeita_zip_que_sai_da_pasta(self):
        with tempfile.TemporaryDirectory() as pasta:
            zip_path = Path(pasta) / "update.zip"
            with zipfile.ZipFile(zip_path, "w") as arquivo:
                arquivo.writestr("../fora.txt", "perigo")
            with zipfile.ZipFile(zip_path) as arquivo, self.assertRaises(ValueError):
                _extrair_zip_seguro(arquivo, Path(pasta) / "destino")
            self.assertFalse((Path(pasta).parent / "fora.txt").exists())

    def test_atualizador_desfaz_copia_parcial(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            origem, destino = raiz / "origem", raiz / "destino"
            origem.mkdir(); destino.mkdir()
            (origem / "a.txt").write_text("novo", encoding="utf-8")
            (origem / "b.txt").write_text("falha", encoding="utf-8")
            (destino / "a.txt").write_text("antigo", encoding="utf-8")
            from updater import _substituir_arquivo as copiar_real
            chamadas = [0]

            def falhar_na_segunda(source, target):
                chamadas[0] += 1
                if chamadas[0] == 2:
                    raise OSError("disco cheio")
                copiar_real(source, target)

            with patch("updater._substituir_arquivo", side_effect=falhar_na_segunda), \
                    self.assertRaises(OSError):
                _copy_update_tree(origem, destino)
            self.assertEqual((destino / "a.txt").read_text(encoding="utf-8"), "antigo")
            self.assertFalse((destino / "b.txt").exists())
