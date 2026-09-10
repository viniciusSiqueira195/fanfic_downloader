"""Destinos de download permitidos por fonte, inclusive redirecionamentos."""
from urllib.parse import urlsplit

HOSTS_POR_FONTE = {
    "Visionvox": {"visionvox.com.br", "www.visionvox.com.br", "visionvox.net", "www.visionvox.net"},
    "Project Gutenberg": {"gutenberg.org", "www.gutenberg.org"},
}


def validar_url_download(url, origem):
    partes = urlsplit(url)
    if (partes.scheme != "https" or partes.hostname not in HOSTS_POR_FONTE.get(origem, set())
            or partes.username or partes.password or partes.port not in (None, 443)):
        raise ValueError(f"O endereço deve ser um link HTTPS da fonte {origem}.")
    return partes
