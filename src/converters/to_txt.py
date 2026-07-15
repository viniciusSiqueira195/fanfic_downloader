import os
import unicodedata
from converters.normalizacao import normalizar

def salvar_txt(titulo, texto, pasta_destino):
    titulo = normalizar(titulo)
    texto = normalizar(texto)

    titulo_limpo = titulo.split(' - ')[0]
    titulo_limpo = unicodedata.normalize('NFKD', titulo_limpo).encode('ascii', 'ignore').decode('utf-8')
    
    nome_arquivo = "".join(c for c in titulo_limpo if c.isalnum() or c == ' ').strip()
    nome_arquivo = " ".join(nome_arquivo.split())
    
    if not nome_arquivo:
        nome_arquivo = "Fanfic_Wattpad"
        
    caminho_completo = os.path.join(pasta_destino, f"{nome_arquivo}.txt")
    
    with open(caminho_completo, 'w', encoding='utf-8') as f:
        f.write(titulo + "\n\n")
        f.write(texto)
        
    return caminho_completo