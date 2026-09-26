from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from ninja import Router
from ninja.errors import HttpError

from apps.accounts import selectors, services
from apps.accounts.permissions import admin_only, authenticated
from apps.accounts.schemas import (
    LoginIn,
    RefreshIn,
    TeacherRegisterIn,
    TokenPairOut,
    UserCreateIn,
    UserOut,
    UserUpdateIn,
)
from core.errors import validation_error
from core.jwt import TokenError, create_token_pair, decode_token


# Un router por audiencia. El permiso se declara aca, una sola vez, y vale para
# todos los endpoints que cuelguen de ese router.
#
# Los endpoints no arman consultas ni escriben en la base: leen con selectors y
# escriben con services. Lo que queda aca es lo unico que es de HTTP: el permiso,
# la forma de la entrada y la traduccion de los errores.

# Sin auth: es la puerta de entrada, todavia no hay token.
public_router = Router(tags=["Autenticacion"])

# Cualquier usuario autenticado, sin importar su rol.
me_router = Router(tags=["Mi cuenta"], auth=authenticated)

# Solo ADMIN.
admin_router = Router(tags=["Administracion de usuarios"], auth=admin_only)


@public_router.post("/login", response=TokenPairOut)
def login(request, payload: LoginIn):
    email = payload.email.strip().lower()
    user = authenticate(request, username=email, password=payload.password)
    if user is None:
        raise HttpError(401, "Credenciales invalidas.")

    return create_token_pair(user)


@public_router.post("/refresh", response=TokenPairOut)
def refresh_token(request, payload: RefreshIn):
    try:
        claims = decode_token(payload.refresh, expected_type="refresh")
    except TokenError as exc:
        raise HttpError(401, str(exc)) from exc

    user = selectors.active_user(claims["sub"])
    if user is None:
        raise HttpError(401, "El usuario del token no existe o esta inactivo.")

    return create_token_pair(user)


@public_router.post("/register/teacher", response=UserOut)
def register_teacher(request, payload: TeacherRegisterIn):
    """Alta publica de un docente. La cuenta no habilita nada hasta que una
    institucion lo acepte: por eso puede estar abierta sin riesgo.

    Es el unico registro abierto de la plataforma: la institucion activa su
    cuenta contra un email que el administrador habilito antes, y el alumno ni
    siquiera tiene cuenta."""
    try:
        return services.register_teacher(**payload.model_dump())
    except ValidationError as exc:
        raise validation_error(exc) from exc


@me_router.get("/me", response=UserOut)
def me(request):
    # request.auth es lo que devolvio JWTAuth.authenticate(): el usuario del token.
    return request.auth


@admin_router.get("/users", response=list[UserOut])
def list_users(request, buscar: str = None):
    return selectors.users(search=buscar)


@admin_router.post("/users", response=UserOut)
def create_user(request, payload: UserCreateIn):
    try:
        return services.create_user(**payload.model_dump())
    except ValidationError as exc:
        raise validation_error(exc) from exc


@admin_router.patch("/users/{user_id}", response=UserOut)
def update_user(request, user_id: int, payload: UserUpdateIn):
    target = selectors.user(user_id)

    # exclude_unset deja solo los campos que el cliente mando de verdad, que es
    # lo que necesita un PATCH para no pisar el resto con valores vacios.
    try:
        return services.update_user(target, changes=payload.model_dump(exclude_unset=True))
    except ValidationError as exc:
        raise validation_error(exc) from exc
