from datetime import datetime
from typing import Optional

from ninja import Schema


class InstitutionIn(Schema):
    name: str
    city: str = ""
    description: str = ""


class InstitutionOut(Schema):
    id: int
    name: str
    city: str
    description: str


class InstitutionActivateIn(Schema):
    """La institucion entra por primera vez: su email habilitado y la
    contrasena que quiere crear."""

    email: str
    password: str
    first_name: str
    last_name: str


class TeacherInviteIn(Schema):
    teacher_email: str


class MembershipRequestIn(Schema):
    institution_id: int


class PublishingPrivilegeIn(Schema):
    """Dar o sacar el privilegio de publicar sin revision.

    Va un booleano y no dos endpoints (/allow y /revoke) porque es una sola
    decision con dos valores: la institucion confia en este docente, o no. Con
    dos endpoints, dar el privilegio dos veces y sacarlo una dejaria en duda
    cual gano.
    """

    allowed: bool


class MembershipOut(Schema):
    id: int
    institution_id: int
    institution_name: str
    teacher_email: str
    teacher_name: str
    origin: str
    status: str
    publishes_without_review: bool
    created_at: datetime
    responded_at: Optional[datetime] = None

    @staticmethod
    def resolve_institution_name(obj):
        return obj.institution.name

    @staticmethod
    def resolve_teacher_email(obj):
        return obj.teacher.email

    @staticmethod
    def resolve_teacher_name(obj):
        return obj.teacher.full_name
