from datetime import timedelta

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from django.conf import settings
from django.utils import timezone


class TokenError(Exception):
    pass


def _serialize_datetime(value):
    return int(value.timestamp())


def _build_payload(user, token_type, lifetime):
    now = timezone.now()
    expires_at = now + lifetime
    return {
        "sub": str(user.pk),
        "email": user.email,
        "role": user.role,
        "type": token_type,
        "iat": _serialize_datetime(now),
        "exp": _serialize_datetime(expires_at),
    }


def create_access_token(user):
    payload = _build_payload(
        user,
        token_type="access",
        lifetime=timedelta(minutes=settings.ACCESS_TOKEN_MINUTES),
    )
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(user):
    payload = _build_payload(
        user,
        token_type="refresh",
        lifetime=timedelta(days=settings.REFRESH_TOKEN_DAYS),
    )
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_token_pair(user):
    return {
        "access": create_access_token(user),
        "refresh": create_refresh_token(user),
        "token_type": "bearer",
    }


def decode_token(token, expected_type=None):
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except ExpiredSignatureError as exc:
        raise TokenError("El token expiro.") from exc
    except InvalidTokenError as exc:
        raise TokenError("El token es invalido.") from exc

    if expected_type and payload.get("type") != expected_type:
        raise TokenError("El tipo de token no coincide con la operacion solicitada.")

    return payload

