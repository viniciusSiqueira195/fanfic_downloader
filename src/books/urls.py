"""Destinos de download permitidos por fonte, inclusive redirecionamentos."""
from urllib.parse import urlsplit

HOSTS_POR_FONTE = {
    "Visionvox": {"visionvox.com.br", "www.visionvox.com.br", "visionvox.net", "www.visionvox.net"},
    "Project Gutenberg": {"gutenberg.org", "www.gutenberg.org"},
    "Wikisource": {"ws-export.wmcloud.org"},
    "Internet Archive": {"archive.org", "www.archive.org"},
}

SUFIXOS_POR_FONTE = {"Internet Archive": (".archive.org",)}


def validar_url_download(url, origem):
    partes = urlsplit(url)
    host = partes.hostname or ""
    permitido = (host in HOSTS_POR_FONTE.get(origem, set())
                 or any(host.endswith(sufixo) for sufixo in SUFIXOS_POR_FONTE.get(origem, ())))
    if (partes.scheme != "https" or not permitido
            or partes.username or partes.password or partes.port not in (None, 443)):
        raise ValueError(f"O endereço deve ser um link HTTPS da fonte {origem}.")
    return partes
