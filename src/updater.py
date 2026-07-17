import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests

from version import APP_VERSION


GITHUB_OWNER = "viniciusSiqueira195"
GITHUB_REPO = "fanfic_downloader"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
USER_AGENT = "fanfic_downloader-updater/1.0"
PRESERVED_RELATIVE_PATHS = {
    Path("config.json"),
    Path("src") / "config.json",
}


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    release_url: str
    asset_name: str
    asset_url: str
    expected_sha256: str


def _parse_version(value):
    cleaned = value.strip()
    if cleaned.lower().startswith("v"):
        cleaned = cleaned[1:]
    parts = re.findall(r"\d+", cleaned)
    if not parts:
        return (0,)
    return tuple(int(part) for part in parts)


def _is_newer_version(latest, current):
    latest_parts = _parse_version(latest)
    current_parts = _parse_version(current)
    length = max(len(latest_parts), len(current_parts))
    latest_parts = latest_parts + (0,) * (length - len(latest_parts))
    current_parts = current_parts + (0,) * (length - len(current_parts))
    return latest_parts > current_parts


def _normalize_sha256(value):
    digest = value.strip()
    if digest.lower().startswith("sha256:"):
        digest = digest.split(":", 1)[1]
    digest = digest.strip()
    if not re.fullmatch(r"[a-fA-F0-9]{64}", digest):
        raise ValueError("Hash SHA-256 inválido na release.")
    return digest.lower()


def _select_asset(assets, suffixes):
    for suffix in suffixes:
        for asset in assets:
            name = asset.get("name", "")
            if name.lower().endswith(suffix.lower()):
                return asset
    return None


def _fetch_latest_release():
    response = requests.get(
        LATEST_RELEASE_URL,
        headers={"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def verificar_atualizacao():
    release = _fetch_latest_release()
    latest_version = release.get("tag_name", "").strip()
    release_url = release.get("html_url", "")
    assets = release.get("assets", [])

    if not latest_version:
        raise ValueError("A release mais recente não informou tag_name.")

    if not _is_newer_version(latest_version, APP_VERSION):
        return None

    archive_asset = _select_asset(assets, [".zip"])
    if archive_asset is None:
        raise ValueError("A release não possui um arquivo .zip para atualização.")

    expected_sha256 = ""
    digest = archive_asset.get("digest", "")
    if digest:
        expected_sha256 = _normalize_sha256(digest)
    else:
        checksum_asset = _select_asset(assets, [".sha256", ".txt"])
        if checksum_asset is not None:
            checksum_text = requests.get(
                checksum_asset["browser_download_url"],
                headers={"User-Agent": USER_AGENT},
                timeout=30,
            ).text
            match = re.search(r"([a-fA-F0-9]{64})", checksum_text)
            if match is None:
                raise ValueError("O arquivo de hash da release não contém um SHA-256 válido.")
            expected_sha256 = match.group(1).lower()

    if not expected_sha256:
        raise ValueError("A release não fornece hash SHA-256 para validação.")

    return UpdateInfo(
        current_version=APP_VERSION,
        latest_version=latest_version,
        release_url=release_url,
        asset_name=archive_asset.get("name", "update.zip"),
        asset_url=archive_asset["browser_download_url"],
        expected_sha256=expected_sha256,
    )


def _download_archive(url, destination_path, expected_sha256, progresso_callback=None):
    hasher = hashlib.sha256()
    with requests.get(url, stream=True, headers={"User-Agent": USER_AGENT}, timeout=60) as response:
        response.raise_for_status()
        total = int(response.headers.get("content-length", "0"))
        downloaded = 0

        with open(destination_path, "wb") as arquivo:
            for chunk in response.iter_content(chunk_size=1024 * 64):
                if not chunk:
                    continue
                arquivo.write(chunk)
                hasher.update(chunk)
                downloaded += len(chunk)
                if progresso_callback is not None and total > 0:
                    percent = int(downloaded * 100 / total)
                    progresso_callback(percent, "Baixando atualização...", -1)

    if hasher.hexdigest().lower() != expected_sha256.lower():
        raise ValueError("O hash SHA-256 da atualização não confere.")


def _extract_payload_root(extracted_root):
    entries = [item for item in extracted_root.iterdir()]
    if len(entries) == 1 and entries[0].is_dir():
        return entries[0]
    return extracted_root


def _is_preserved(relative_path):
    normalized = Path(relative_path)
    for preserved in PRESERVED_RELATIVE_PATHS:
        if normalized.parts == preserved.parts:
            return True
    return False


def _copy_update_tree(source_root, target_root):
    for source_path in source_root.rglob("*"):
        if source_path.is_dir():
            continue
        relative_path = source_path.relative_to(source_root)
        if _is_preserved(relative_path):
            continue
        destination_path = target_root / relative_path
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, destination_path)


def get_application_root():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def get_restart_command():
    if getattr(sys, "frozen", False):
        return [sys.executable]
    entry_point = get_application_root() / "src" / "main.py"
    return [sys.executable, str(entry_point)]


def baixar_e_aplicar_atualizacao(update_info, progresso_callback=None):
    application_root = get_application_root()
    with tempfile.TemporaryDirectory() as temp_dir:
        archive_path = Path(temp_dir) / update_info.asset_name
        _download_archive(update_info.asset_url, archive_path, update_info.expected_sha256, progresso_callback)

        if progresso_callback is not None:
            progresso_callback(100, "Validando e aplicando atualização...", -1)

        with tempfile.TemporaryDirectory() as extract_dir:
            extract_path = Path(extract_dir)
            with zipfile.ZipFile(archive_path, "r") as archive:
                archive.extractall(extract_path)
            payload_root = _extract_payload_root(extract_path)
            _copy_update_tree(payload_root, application_root)

    return get_restart_command()


def reiniciar_aplicativo(restart_command):
    subprocess.Popen(restart_command, cwd=str(get_application_root()))
