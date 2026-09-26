from ninja.errors import HttpError
from ninja.security import HttpBearer

from django.contrib.auth import get_user_model

from core.jwt import TokenError, decode_token


class JWTAuth(HttpBearer):
    """Autenticacion: responde QUIEN esta haciendo el pedido.

    Django Ninja llama a authenticate() antes del endpoint, con el token que
    venia en el header Authorization: Bearer <token>. Lo que devuelve este
    metodo queda disponible como request.auth dentro del endpoint.

    Devolver None seria un 401 generico; preferimos levantar HttpError con un
    mensaje que explique que paso (token vencido, usuario inactivo).
    """

    allowed_roles = ()

    def authenticate(self, request, token):
        try:
            payload = decode_token(token, expected_type="access")
        except TokenError as exc:
            raise HttpError(401, str(exc)) from exc

        user_model = get_user_model()
        try:
            user = user_model.objects.get(pk=payload["sub"], is_active=True)
        except user_model.DoesNotExist as exc:
            raise HttpError(401, "El usuario del token no existe o esta inactivo.") from exc

        self.check_roles(user)

        request.user = user
        request.jwt_payload = payload
        return user

    def check_roles(self, user):
        """Autorizacion: responde QUE puede hacer ese usuario.

        Sin roles declarados alcanza con estar autenticado. La distincion entre
        401 y 403 importa: 401 es "no se quien sos", 403 es "se quien sos, pero
        esto no te corresponde".
        """
        if self.allowed_roles and user.role not in self.allowed_roles:
            permitidos = ", ".join(self.allowed_roles)
            raise HttpError(403, f"Esta operacion requiere alguno de estos roles: {permitidos}.")


class RoleAuth(JWTAuth):
    """Misma autenticacion, pero ademas exige uno de los roles indicados.

    Se usa a nivel de router, no de endpoint: asi el permiso se declara una vez
    para todo un grupo de operaciones y no se puede olvidar en una.
    """

    def __init__(self, *roles):
        super().__init__()
        self.allowed_roles = tuple(roles)