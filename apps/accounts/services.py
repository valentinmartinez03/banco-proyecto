"""Operaciones que modifican usuarios.

Un service es una funcion con nombre de lo que hace en el negocio ("crear
usuario"), no de lo que hace en la base ("insert"). Valida, escribe y devuelve el
objeto; los errores de negocio salen como ValidationError y la capa de API los
traduce a un 400.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.accounts.models import UserRole


def _validate_role(role):
    if role not in UserRole.values:
        raise ValidationError({"role": f"Rol invalido. Opciones: {', '.join(UserRole.values)}."})


def create_user(*, email, password, first_name, last_name, role):
    _validate_role(role)
    try:
        return get_user_model().objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=role,
        )
    except ValueError as exc:
        # El manager avisa con ValueError; hacia afuera todo error de negocio
        # viaja como ValidationError, para que la API tenga una sola traduccion.
        raise ValidationError({"email": str(exc)}) from exc


def register_teacher(*, email, password, first_name, last_name):
    """Alta publica de un docente.

    La cuenta sola no habilita nada: recien cuando una institucion acepta su
    solicitud (o el docente acepta una invitacion) aparece lo que puede hacer.
    Por eso este registro puede ser publico sin riesgo.
    """
    return create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        role=UserRole.TEACHER,
    )


def update_user(user, *, changes):
    """Aplica solo los campos que llegaron. La contrasena nunca se asigna
    directo: pasa por set_password para quedar hasheada."""
    if "role" in changes:
        _validate_role(changes["role"])

    password = changes.pop("password", None)
    for field, value in changes.items():
        setattr(user, field, value)

    if password:
        user.set_password(password)

    try:
        user.save()
    except ValueError as exc:
        raise ValidationError({"email": str(exc)}) from exc

    return user
