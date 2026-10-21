"""Consultas de lectura del catalogo de tecnologias.

La API no arma querysets: pide lo que necesita por nombre. Aca hay dos
consultas y nada mas, porque las tecnologias se cargan desde el admin y lo
unico que la plataforma hace con ellas es listarlas y buscarlas por id.
"""
from django.shortcuts import get_object_or_404

from apps.catalogs.models import Technology


def technologies(search=None):
    """Todas las tecnologias, o las que contengan ese texto en el nombre.

    El orden lo pone el ordering del modelo (alfabetico), que es el que espera
    quien mira una lista de opciones para filtrar.

    El filtro va aca y no en un managers.py propio: los managers valen cuando
    el mismo filtro se repite en varias consultas, y este se usa una sola vez.
    """
    queryset = Technology.objects.all()
    if search:
        queryset = queryset.filter(name__icontains=search)
    return queryset


def technology(technology_id):
    """Devuelve la tecnologia o corta con un 404."""
    return get_object_or_404(Technology, pk=technology_id)
