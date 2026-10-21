from django.core.exceptions import ValidationError
from ninja import Router
from ninja.errors import HttpError

from apps.accounts.models import UserRole
from apps.accounts.permissions import admin_only, institution_or_admin, teacher_or_admin
from apps.accounts.schemas import UserOut
from apps.institutions import selectors, services
from apps.institutions.models import MembershipOrigin, MembershipStatus
from apps.institutions.schemas import (
    InstitutionActivateIn,
    InstitutionIn,
    InstitutionOut,
    MembershipOut,
    MembershipRequestIn,
    PublishingPrivilegeIn,
    TeacherInviteIn,
)
from core.errors import validation_error


# Lectura publica: navegar la plataforma y armar filtros no piden token.
public_router = Router(tags=["Instituciones"])

# La cuenta institucional: sus docentes y sus decisiones.
institution_router = Router(tags=["Mi institucion"], auth=institution_or_admin)

# El docente: sus relaciones con instituciones.
teacher_router = Router(tags=["Instituciones del docente"], auth=teacher_or_admin)

# Alta directa: solo administradores (los emails habilitados van por el admin).
admin_router = Router(tags=["Administracion de instituciones"], auth=admin_only)


def current_institution(user):
    """La institucion a cargo del usuario autenticado.

    Es la misma idea que ensure_project_of_institution en proyectos:
    autorizacion a nivel de objeto, que el rol del router no alcanza a
    responder. La usan academics (para saber de quien son las carreras y las
    cursadas) y projects (para saber que proyectos le toca revisar).
    """
    institution = selectors.institution_managed_by(user)
    if institution is None:
        raise HttpError(403, "La cuenta no esta a cargo de ninguna institucion.")
    return institution


def ensure_membership_of_institution(user, membership):
    """La relacion tiene que ser de la institucion que hace el pedido.

    Es distinto de ensure_can_respond: eso mira de que lado nacio la relacion
    para saber a quien le toca contestar; esto mira de quien es. El privilegio
    de publicar sin revision lo da la institucion y nadie mas, asi que alcanza
    con comprobar que la membresia sea suya.
    """
    if user.role == UserRole.ADMIN:
        return
    institution = current_institution(user)
    if membership.institution_id != institution.id:
        raise HttpError(403, "La relacion pertenece a otra institucion.")


def ensure_can_respond(user, membership):
    """Una invitacion la responde el docente invitado; una solicitud, la
    institucion que la recibio. El administrador puede destrabar cualquiera."""
    if user.role == UserRole.ADMIN:
        return
    if membership.origin == MembershipOrigin.INVITATION:
        if membership.teacher_id != user.id:
            raise HttpError(403, "Solo el docente invitado puede responder esta invitacion.")
    else:
        institution = current_institution(user)
        if membership.institution_id != institution.id:
            raise HttpError(403, "La solicitud pertenece a otra institucion.")


# --------------------------------------------------------------------------
# Publico
# --------------------------------------------------------------------------

@public_router.get("/institutions", response=list[InstitutionOut])
def list_institutions(request, buscar: str = None):
    return selectors.institutions(search=buscar)


@public_router.post("/institutions/activate", response=UserOut)
def activate_institution_account(request, payload: InstitutionActivateIn):
    """La institucion cuyo email fue habilitado desde el admin entra por
    primera vez y crea su contrasena."""
    try:
        return services.activate_institution_account(**payload.model_dump())
    except ValidationError as exc:
        raise validation_error(exc) from exc


# --------------------------------------------------------------------------
# Cuenta institucional
# --------------------------------------------------------------------------

@institution_router.get("/teachers", response=list[MembershipOut])
def list_institution_teachers(request, status: str = None):
    institution = current_institution(request.auth)
    return selectors.memberships_of_institution(institution, status=status)


@institution_router.post("/teachers/invite", response=MembershipOut)
def invite_teacher(request, payload: TeacherInviteIn):
    institution = current_institution(request.auth)
    try:
        return services.invite_teacher(institution, teacher_email=payload.teacher_email)
    except ValidationError as exc:
        raise validation_error(exc) from exc


@institution_router.post("/teachers/{membership_id}/accept", response=MembershipOut)
def accept_teacher_request(request, membership_id: int):
    membership = selectors.membership(membership_id)
    ensure_can_respond(request.auth, membership)
    try:
        return services.respond_membership(membership, status=MembershipStatus.ACCEPTED)
    except ValidationError as exc:
        raise validation_error(exc) from exc


@institution_router.post("/teachers/{membership_id}/reject", response=MembershipOut)
def reject_teacher_request(request, membership_id: int):
    membership = selectors.membership(membership_id)
    ensure_can_respond(request.auth, membership)
    try:
        return services.respond_membership(membership, status=MembershipStatus.REJECTED)
    except ValidationError as exc:
        raise validation_error(exc) from exc


@institution_router.put("/teachers/{membership_id}/publishing", response=MembershipOut)
def set_publishing_privilege(request, membership_id: int, payload: PublishingPrivilegeIn):
    """Le da o le saca a un docente el permiso de publicar sin revision."""
    membership = selectors.membership(membership_id)
    ensure_membership_of_institution(request.auth, membership)
    try:
        return services.set_publishing_privilege(membership, allowed=payload.allowed)
    except ValidationError as exc:
        raise validation_error(exc) from exc


# --------------------------------------------------------------------------
# Docente
# --------------------------------------------------------------------------

@teacher_router.get("/memberships", response=list[MembershipOut])
def list_my_memberships(request, status: str = None):
    return selectors.memberships_of_teacher(request.auth, status=status)


@teacher_router.post("/memberships", response=MembershipOut)
def request_membership(request, payload: MembershipRequestIn):
    try:
        return services.request_membership(request.auth, institution_id=payload.institution_id)
    except ValidationError as exc:
        raise validation_error(exc) from exc


@teacher_router.post("/memberships/{membership_id}/accept", response=MembershipOut)
def accept_invitation(request, membership_id: int):
    membership = selectors.membership(membership_id)
    ensure_can_respond(request.auth, membership)
    try:
        return services.respond_membership(membership, status=MembershipStatus.ACCEPTED)
    except ValidationError as exc:
        raise validation_error(exc) from exc


@teacher_router.post("/memberships/{membership_id}/reject", response=MembershipOut)
def reject_invitation(request, membership_id: int):
    membership = selectors.membership(membership_id)
    ensure_can_respond(request.auth, membership)
    try:
        return services.respond_membership(membership, status=MembershipStatus.REJECTED)
    except ValidationError as exc:
        raise validation_error(exc) from exc


# --------------------------------------------------------------------------
# Administrador
# --------------------------------------------------------------------------

@admin_router.post("/institutions", response=InstitutionOut)
def create_institution(request, payload: InstitutionIn):
    try:
        return services.create_institution(**payload.model_dump())
    except ValidationError as exc:
        raise validation_error(exc) from exc
