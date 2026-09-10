"""Registro de catálogos disponíveis na interface."""
from books.gutenberg import Gutenberg
from books.visionvox import Visionvox

FONTES = {"Visionvox": Visionvox, "Project Gutenberg": Gutenberg}
