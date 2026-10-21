"""Consultas de lectura de instituciones y de la relacion con sus docentes."""
from django.shortcuts import get_object_or_404

from apps.institutions.models import Institution, InstitutionEmailRule, InstitutionTeacher


def institutions(search=None):
    """Lo que ve cualquiera: la lista para navegar y armar filtros."""
    queryset = Institution.objects.all()
    if search:
        queryset = queryset.search(search)
    return queryset


def institution(institution_id):
    return get_object_or_404(Institution, pk=institution_id)


def email_rule_for(email):
    """La regla que habilita ese email institucional, o None."""
    return InstitutionEmailRule.objects.select_related("institution").filter(
        email__iexact=email.strip()
    ).first()


def institution_managed_by(user):
    """La institucion a cargo del usuario, o None.

    Pasa por la regla de email y no por un campo en User: si un administrador
    borra la regla desde el admin, ese acceso se revoca solo.
    """
    return Institution.objects.filter(email_rules__user=user).first()


def membership(membership_id):
    return get_object_or_404(
        InstitutionTeacher.objects.with_related(), pk=membership_id
    )


def memberships_of_institution(institution, status=None):
    queryset = InstitutionTeacher.objects.of_institution(institution).with_related()
    if status:
        queryset = queryset.filter(status=status.upper())
    return queryset


def memberships_of_teacher(teacher, status=None):
    queryset = InstitutionTeacher.objects.of_teacher(teacher).with_related()
    if status:
        queryset = queryset.filter(status=status.upper())
    return queryset


def accepted_membership(teacher, institution):
    """La membresia aceptada del docente en esa institucion, o None.

    Es LA pregunta de permisos del docente: la usan las cursadas y toda accion
    que un docente quiera hacer en nombre de una institucion.
    """
    return (
        InstitutionTeacher.objects.accepted()
        .of_teacher(teacher)
        .of_institution(institution)
        .first()
    )


def teacher_publishes_without_review(teacher, institution):
    """Si esa institucion le permite a ese docente publicar sin revision.

    La pregunta la hace `projects` cada vez que se crea o se edita un proyecto,
    y se responde aca porque el dato es de la membresia: quien confia es la
    institucion, no el proyecto. Sin membresia aceptada la respuesta es que no,
    sin caso especial: un docente que no pertenece a la institucion tampoco
    llega a cargar un proyecto suyo.
    """
    membership = accepted_membership(teacher, institution)
    return membership is not None and membership.publishes_without_review
