from typing import Optional

from ninja import Schema


class LoginIn(Schema):
    email: str
    password: str


class RefreshIn(Schema):
    refresh: str


class TokenPairOut(Schema):
    access: str
    refresh: str
    token_type: str


class UserOut(Schema):
    id: int
    email: str
    first_name: str
    last_name: str
    role: str
    is_active: bool


class UserCreateIn(Schema):
    email: str
    first_name: str
    last_name: str
    password: str
    role: str


class UserUpdateIn(Schema):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class TeacherRegisterIn(Schema):
    """Alta publica de un docente: la cuenta nace sin institucion."""

    email: str
    first_name: str
    last_name: str
    password: str
