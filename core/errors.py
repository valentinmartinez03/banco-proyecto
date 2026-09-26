"""Traduccion de errores de negocio a errores HTTP.

Los services no saben que existe HTTP: cuando algo no cumple una regla levantan
un ValidationError de Django. Este es el unico lugar donde ese error se convierte
en una respuesta 400, y lo comparten todas las apps.
"""
from ninja.errors import HttpError


def validation_error(exc):
    """Devuelve el HttpError 400 equivalente a un ValidationError.

    HttpError espera un texto: si se le pasa el diccionario de errores tal cual,
    Ninja rompe al armar la respuesta.
    """
    if hasattr(exc, "message_dict"):
        detalles = "; ".join(
            f"{campo}: {' '.join(mensajes)}" for campo, mensajes in exc.message_dict.items()
        )
    else:
        detalles = " ".join(exc.messages)
    return HttpError(400, detalles)
