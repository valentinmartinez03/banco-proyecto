"""Consultas de lectura de la app de cuentas.

Los endpoints no arman querysets: piden lo que necesitan por nombre. Asi la
misma consulta se reusa desde la API, desde un comando o desde un test, y si
manana hay que agregarle un filtro se cambia en un solo lugar.
"""
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404


def users(search=None):
    queryset = get_user_model().objects.all()
    if search:
        queryset = queryset.search(search)
    return queryset


def user(user_id):
    """Devuelve el usuario o corta con un 404."""
    return get_object_or_404(get_user_model(), pk=user_id)


def active_user(user_id):
    """Devuelve el usuario activo o None.

    A diferencia de user(), no corta con un 404: quien la llama es el refresh
    del token, que ante un usuario inexistente o dado de baja tiene que responder
    401. Que error corresponde es una decision de la API, no del selector.
    """
    return get_user_model().objects.active().filter(pk=user_id).first()
