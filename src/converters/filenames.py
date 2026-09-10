"""Nomes portáveis, preservando acentos e evitando dispositivos do Windows."""
import re
from converters.normalizacao import normalizar


def nome_seguro(titulo):
    nome = re.sub(r'[\x00-\x1f\\/:*?"<>|]', "", normalizar(titulo)).strip().rstrip(". ")
    nome = nome[:140].rstrip(". ") or "Livro"
    if nome.split(".", 1)[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
        nome = "_" + nome
    return nome
