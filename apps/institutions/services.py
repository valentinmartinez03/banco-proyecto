"""Operaciones que modifican instituciones y su relacion con los docentes.

Leyendo esta lista de funciones se entiende el circuito completo sin abrir la
API: el administrador crea la institucion y habilita emails, la institucion
activa su cuenta, y la relacion con un docente nace por invitacion o por
solicitud y se responde del lado que corresponda.
"""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounts import services as accounts_services
from apps.accounts.models import UserRole
from apps.institutions import selectors
from apps.institutions.models import (
    Institution,
    InstitutionTeacher,
    MembershipOrigin,
    MembershipStatus,
)


def create_institution(*, name, city="", description=""):
    """Alta directa de un administrador. Los emails habilitados se cargan
    despues, desde el admin de Django."""
    return Institution.objects.create(
        name=name.strip(),
        city=city.strip(),
        description=description,
    )


@transaction.atomic
def activate_institution_account(*, email, password, first_name, last_name):
    """La institucion entra por primera vez y crea su contrasena.

    Solo funciona si un administrador habilito ese email exacto desde el admin
    (InstitutionEmailRule). La regla queda apuntando al usuario creado: asi se
    sabe que ya fue usada y borrarla revoca el acceso.
    """
    rule = selectors.email_rule_for(email)
    if rule is None:
        raise ValidationError({"email": "El email no esta habilitado para ninguna institucion."})
    if rule.is_activated:
        raise ValidationError({"email": "Ese email ya activo su cuenta institucional."})

    user = accounts_services.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        role=UserRole.INSTITUTION,
    )
    rule.user = user
    rule.save(update_fields=["user"])
    return user


def _ensure_no_membership(institution, teacher):
    existing = InstitutionTeacher.objects.of_institution(institution).of_teacher(teacher).first()
    if existing is not None:
        raise ValidationError(
            {"teacher": f"Ya existe una relacion con ese docente y esta {existing.get_status_display().lower()}."}
        )


def invite_teacher(institution, *, teacher_email):
    """La institucion invita a un docente ya registrado, por su email."""
    teacher = (
        get_user_model().objects.active()
        .with_role(UserRole.TEACHER)
        .filter(email__iexact=teacher_email.strip())
        .first()
    )
    if teacher is None:
        raise ValidationError(
            {"teacher_email": "No hay un docente registrado con ese email. El docente debe crear su cuenta primero."}
        )

    _ensure_no_membership(institution, teacher)
    return InstitutionTeacher.objects.create(
        institution=institution,
        teacher=teacher,
        origin=MembershipOrigin.INVITATION,
    )


def request_membership(teacher, *, institution_id):
    """El docente pide formar parte de una institucion."""
    institution = selectors.institution(institution_id)
    _ensure_no_membership(institution, teacher)
    return InstitutionTeacher.objects.create(
        institution=institution,
        teacher=teacher,
        origin=MembershipOrigin.REQUEST,
    )


def set_publishing_privilege(membership, *, allowed):
    """La institucion decide si le cree a este docente sin revisarle lo que sube.

    Es el atajo que evita que un docente de confianza espere una aprobacion que
    va a llegar siempre: con el privilegio puesto, sus proyectos nacen
    aprobados. La institucion no pierde el control, lo mueve de lugar: sigue
    pudiendo revisar cualquier proyecto despues de publicado y sigue pudiendo
    sacarle el privilegio.

    Solo se le da a una relacion aceptada: mientras la membresia este pendiente
    o rechazada, el docente no puede cargar nada, y un privilegio guardado ahi
    seria una decision tomada sobre alguien que todavia no entro.
    """
    if membership.status != MembershipStatus.ACCEPTED:
        raise ValidationError(
            {"teacher": "El privilegio solo se le da a un docente con la relacion aceptada."}
        )
    return membership.set_publishing_privilege(allowed)


def respond_membership(membership, *, status):
    """Acepta o rechaza una relacion pendiente.

    Quien puede responder (el docente si fue invitacion, la institucion si fue
    solicitud) lo decide la capa de API: eso es autorizacion. Aca queda la regla
    de negocio: solo se responde lo pendiente y solo con un estado valido.
    """
    if status not in {MembershipStatus.ACCEPTED, MembershipStatus.REJECTED}:
        raise ValidationError({"status": "Estado invalido: se acepta o se rechaza."})
    if membership.status != MembershipStatus.PENDING:
        raise ValidationError({"status": "La relacion ya fue respondida."})
    return membership.respond(status)
