"""Classificação local dos resultados retornados pelas fontes de fanfics."""
import re
import unicodedata

PALAVRAS_VAZIAS = {"a", "ao", "aos", "as", "da", "das", "de", "do", "dos", "e", "em", "na", "nas", "no", "nos", "o", "os", "um", "uma"}
PORTUGUES = {"ainda", "assim", "ate", "bem", "com", "depois", "ela", "ele", "eles", "essa", "esse", "foi", "mais", "mas", "muito", "nao", "para", "pela", "pelo", "por", "porque", "quando", "que", "se", "sem", "seu", "sua", "tambem", "tem", "uma", "voce"}
ESPANHOL = {"aunque", "con", "cuando", "del", "desde", "ella", "ellos", "hasta", "los", "mas", "muy", "para", "pero", "porque", "que", "sin", "sus", "tambien", "tiene", "una"}
INGLES = {"after", "and", "because", "before", "but", "for", "from", "has", "have", "her", "his", "into", "more", "not", "she", "that", "the", "their", "them", "then", "they", "this", "very", "was", "when", "where", "with", "you"}


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c)).casefold()
    return " ".join(re.findall(r"[a-z0-9]+", texto))


def termos_significativos(termo):
    todos = normalizar(termo).split()
    relevantes = [token for token in todos if token not in PALAVRAS_VAZIAS]
    return relevantes or todos


def pontuar_resultado(item, termo):
    consulta = normalizar(termo)
    tokens = termos_significativos(termo)
    titulo = normalizar(item.get("titulo"))
    autor = normalizar(item.get("autor"))
    url = normalizar(item.get("url"))
    palavras = set(f"{titulo} {autor} {url}".split())
    if not tokens or not all(token in palavras for token in tokens):
        return 0
    pontos = 100
    if consulta and consulta in titulo:
        pontos += 100
    elif all(token in titulo.split() for token in tokens):
        pontos += 70
    if consulta == titulo:
        pontos += 50
    if consulta and consulta in autor:
        pontos += 40
    return pontos


def idioma_provavelmente_estrangeiro(texto):
    palavras = normalizar(texto).split()
    if len(palavras) < 5:
        return False
    pt = sum(p in PORTUGUES for p in palavras)
    estrangeiro = max(sum(p in ESPANHOL for p in palavras), sum(p in INGLES for p in palavras))
    return estrangeiro >= 3 and estrangeiro >= pt + 2


def filtrar_e_ordenar(resultados, termo, limite):
    classificados = []
    for ordem, item in enumerate(resultados):
        pontos = pontuar_resultado(item, termo)
        texto = " ".join((item.get("titulo", ""), item.get("descricao", "")))
        if pontos and not idioma_provavelmente_estrangeiro(texto):
            classificados.append((-pontos, ordem, item))
    classificados.sort(key=lambda valor: (valor[0], valor[1]))
    return [item for _, _, item in classificados[:limite]]
