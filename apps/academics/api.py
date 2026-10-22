from django.core.exceptions import ValidationError
from ninja import Router
from ninja.errors import HttpError

from apps.academics import selectors, services
from apps.academics.schemas import (
    CareerIn,
    CareerOut,
    CourseIn,
    CourseOut,
    EnrollmentOut,
    EnrollStudentIn,
)
from apps.accounts.models import UserRole
from apps.accounts.permissions import institution_or_admin, teacher_or_admin
from apps.institutions.api import current_institution
from core.errors import validation_error


# Lectura publica: las carreras alimentan el filtro del catalogo de proyectos.
public_router = Router(tags=["Carreras"])

# La institucion administra sus carreras y mira las cursadas de sus docentes.
institution_router = Router(tags=["Carreras de mi institucion"], auth=institution_or_admin)

# El docente administra sus cursadas y los alumnos de cada una.
teacher_router = Router(tags=["Cursadas del docente"], auth=teacher_or_admin)


def ensure_course_teacher(user, course):
    """Permiso a nivel de objeto: cada docente toca solo sus cursadas.

    El router ya pregunto por el rol; esto responde lo que el rol no puede
    saber, que es de quien es esta cursada en particular.
    """
    if user.role == UserRole.ADMIN:
        return
    if course.teacher_id != user.id:
        raise HttpError(403, "Solo el docente de la cursada puede hacer esto.")


def ensure_course_of_institution(user, course):
    """La institucion toca solo las cursadas de sus propias carreras.

    Es la misma pregunta de arriba, para el otro actor. La hace projects cuando
    la institucion carga un proyecto directo, sin pasar por el docente.
    """
    if user.role == UserRole.ADMIN:
        return
    institution = current_institution(user)
    if course.career.institution_id != institution.id:
        raise HttpError(403, "La cursada pertenece a otra institucion.")


# --------------------------------------------------------------------------
# Publico
# --------------------------------------------------------------------------

@public_router.get("/careers", response=list[CareerOut])
def list_careers(request, institution_id: int = None, search: str = None):
    return selectors.careers(institution_id=institution_id, search=search)


# --------------------------------------------------------------------------
# Institucion
# --------------------------------------------------------------------------

@institution_router.get("/careers", response=list[CareerOut])
def list_my_careers(request):
    institution = current_institution(request.auth)
    return selectors.careers(institution_id=institution.id)


@institution_router.post("/careers", response=CareerOut)
def create_career(request, payload: CareerIn):
    institution = current_institution(request.auth)
    try:
        return services.create_career(institution, **payload.model_dump())
    except ValidationError as exc:
        raise validation_error(exc) from exc


@institution_router.get("/courses", response=list[CourseOut])
def list_institution_courses(request):
    institution = current_institution(request.auth)
    return selectors.courses_of_institution(institution)


# --------------------------------------------------------------------------
# Docente
# --------------------------------------------------------------------------

@teacher_router.get("/courses", response=list[CourseOut])
def list_my_courses(request):
    return selectors.courses_of_teacher(request.auth)


@teacher_router.post("/courses", response=CourseOut)
def create_course(request, payload: CourseIn):
    try:
        return services.create_course(request.auth, **payload.model_dump())
    except ValidationError as exc:
        raise validation_error(exc) from exc


@teacher_router.get("/courses/{course_id}/students", response=list[EnrollmentOut])
def list_course_students(request, course_id: int):
    course = selectors.course(course_id)
    ensure_course_teacher(request.auth, course)
    return selectors.enrollments_of_course(course)


@teacher_router.post("/courses/{course_id}/students", response=EnrollmentOut)
def enroll_student(request, course_id: int, payload: EnrollStudentIn):
    course = selectors.course(course_id)
    ensure_course_teacher(request.auth, course)
    try:
        return services.enroll_student(course, **payload.model_dump())
    except ValidationError as exc:
        raise validation_error(exc) from exc


@teacher_router.delete("/courses/{course_id}/students/{enrollment_id}")
def remove_enrollment(request, course_id: int, enrollment_id: int):
    course = selectors.course(course_id)
    ensure_course_teacher(request.auth, course)

    # La inscripcion se busca dentro de la cursada: un id de otra comision da
    # 404 y no llega nunca al service.
    enrollment = selectors.enrollment(course, enrollment_id)
    try:
        services.remove_enrollment(enrollment)
    except ValidationError as exc:
        raise validation_error(exc) from exc
    return {"success": True}
