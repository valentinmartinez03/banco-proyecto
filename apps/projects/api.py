"""Los endpoints de proyectos, agrupados por audiencia.

Un router por actor y el permiso declarado en el router, no en cada funcion: el
rol se pregunta una sola vez, al entrar. Lo que el rol no alcanza a responder
(de que docente es esta cursada, de que institucion es este proyecto) se
pregunta despues, a nivel de objeto, con las dos funciones de mas abajo.

Aca no hay ni un .filter( ni un .create(: leer es tarea de los selectors y
escribir de los services. Lo unico propio de esta capa es traducir: del HTTP al
service, y del ValidationError del service al 400 de la respuesta.
"""
from django.core.exceptions import ValidationError
from ninja import File, Form, Query, Router
from ninja.errors import HttpError
from ninja.files import UploadedFile

from apps.academics import selectors as academics_selectors
from apps.academics.api import ensure_course_of_institution, ensure_course_teacher
from apps.accounts.models import UserRole
from apps.accounts.permissions import institution_or_admin, teacher_or_admin
from apps.institutions.api import current_institution
from apps.projects import selectors, services
from apps.projects.models import ProjectStatus
from apps.projects.schemas import (
    ProjectAssetOut,
    ProjectCreateIn,
    ProjectFilters,
    ProjectLinkIn,
    ProjectLinkOut,
    ProjectOut,
    ProjectReviewIn,
    ProjectSummaryOut,
    ProjectUpdateIn,
)
from core.errors import validation_error


# Lectura publica: cualquiera puede ver el catalogo aprobado, sin token.
public_router = Router(tags=["Catalogo publico"])

# El docente carga los proyectos de sus cursadas y los mantiene.
teacher_router = Router(tags=["Proyectos del docente"], auth=teacher_or_admin)

# La institucion carga proyectos en sus cursadas y revisa los que cargan sus docentes.
institution_router = Router(tags=["Proyectos de mi institucion"], auth=institution_or_admin)


def ensure_project_teacher(user, project):
    """Permiso a nivel de objeto: cada docente toca solo los proyectos de sus
    cursadas.

    El router ya comprobo que sea docente; esto comprueba que sea EL docente.
    Se pregunta por la cursada porque es donde vive el dato: el proyecto no
    guarda a quien lo cargo, guarda en que comision se hizo.

    Vive en la capa de API y no en el service a proposito: es una decision de
    autorizacion, no una regla del negocio. El comando que carga datos de
    ejemplo usa los mismos services sin tener ningun usuario autenticado.
    """
    if user.role == UserRole.ADMIN:
        return
    if project.course.teacher_id != user.id:
        raise HttpError(403, "El proyecto es de la cursada de otro docente.")


def ensure_project_of_institution(user, project):
    """La institucion solo revisa proyectos de sus propias carreras.

    Es la misma pregunta que se hace sobre la cursada al cargar: de quien es la
    carrera. Por eso se contesta con la misma funcion, y no con una copia.
    """
    ensure_course_of_institution(user, project.course)


# --------------------------------------------------------------------------
# Publico
# --------------------------------------------------------------------------

@public_router.get("/projects", response=list[ProjectSummaryOut])
def list_projects(request, filters: ProjectFilters = Query(...)):
    """El catalogo: solo lo aprobado, con los filtros que hayan venido."""
    return selectors.public_catalog(filters)


@public_router.get("/projects/{slug}", response=ProjectOut)
def get_project(request, slug: str):
    """La ficha: el proyecto completo, con sus alumnos, sus archivos y sus links."""
    return selectors.approved_project(slug)


# --------------------------------------------------------------------------
# Docente
# --------------------------------------------------------------------------

@teacher_router.get("/projects", response=list[ProjectSummaryOut])
def list_my_projects(request, filters: ProjectFilters = Query(...)):
    """Los proyectos de las cursadas del docente, en cualquier estado."""
    return selectors.projects_of_teacher(request.auth, filters)


@teacher_router.get("/projects/{project_id}", response=ProjectOut)
def get_my_project(request, project_id: int):
    """La ficha completa de un proyecto propio, en el estado en el que este.

    Es la unica forma que tiene el docente de leer la devolucion de la
    institucion: la ficha publica sirve solo lo aprobado, asi que un proyecto
    devuelto no se puede mirar por ahi, y la lista contesta la version corta,
    que no la incluye.
    """
    project = selectors.project(project_id)
    ensure_project_teacher(request.auth, project)

    return selectors.full_project(project.pk)


@teacher_router.post("/projects", response=ProjectOut)
def create_project(request, payload: ProjectCreateIn):
    """Carga un proyecto en una cursada del docente.

    El permiso se comprueba sobre la cursada antes de llamar al service, con la
    misma funcion que usa academics: un docente no puede cargar un trabajo en la
    comision de otro.
    """
    course = academics_selectors.course(payload.course_id)
    ensure_course_teacher(request.auth, course)

    try:
        project = services.create_project(**payload.model_dump())
    except ValidationError as exc:
        raise validation_error(exc) from exc

    return selectors.full_project(project.pk)


@teacher_router.patch("/projects/{project_id}", response=ProjectOut)
def update_project(request, project_id: int, payload: ProjectUpdateIn):
    project = selectors.project(project_id)
    ensure_project_teacher(request.auth, project)

    try:
        # exclude_unset deja solo los campos que el cliente mando de verdad: sin
        # esto, no se podria distinguir "no toques el resumen" de "borralo".
        services.update_project(project, changes=payload.model_dump(exclude_unset=True))
    except ValidationError as exc:
        raise validation_error(exc) from exc

    return selectors.full_project(project.pk)


@teacher_router.post("/projects/{project_id}/assets", response=ProjectAssetOut)
def upload_asset(
    request,
    project_id: int,
    asset_type: str = Form(...),
    title: str = Form(""),
    is_cover: bool = Form(False),
    file: UploadedFile = File(...),
):
    """Sube una imagen o un documento del proyecto.

    El archivo viaja como multipart/form-data y no como JSON, y por eso los
    parametros se declaran con Form(...) y File(...) en vez de con un schema.
    """
    project = selectors.project(project_id)
    ensure_project_teacher(request.auth, project)

    try:
        return services.upload_asset(
            project,
            asset_type=asset_type,
            title=title,
            file=file,
            is_cover=is_cover,
        )
    except ValidationError as exc:
        raise validation_error(exc) from exc


@teacher_router.delete("/projects/{project_id}/assets/{asset_id}")
def delete_asset(request, project_id: int, asset_id: int):
    project = selectors.project(project_id)
    ensure_project_teacher(request.auth, project)

    services.delete_asset(selectors.asset(project, asset_id))
    return {"success": True}


@teacher_router.post("/projects/{project_id}/links", response=ProjectLinkOut)
def add_link(request, project_id: int, payload: ProjectLinkIn):
    """Suma el repositorio, la demo, el video o lo que el trabajo tenga afuera."""
    project = selectors.project(project_id)
    ensure_project_teacher(request.auth, project)

    try:
        return services.add_link(project, **payload.model_dump())
    except ValidationError as exc:
        raise validation_error(exc) from exc


@teacher_router.delete("/projects/{project_id}/links/{link_id}")
def delete_link(request, project_id: int, link_id: int):
    project = selectors.project(project_id)
    ensure_project_teacher(request.auth, project)

    services.delete_link(selectors.link(project, link_id))
    return {"success": True}


# --------------------------------------------------------------------------
# Institucion
# --------------------------------------------------------------------------

@institution_router.get("/projects", response=list[ProjectSummaryOut])
def list_institution_projects(request, status: str = None):
    """Los proyectos de las carreras de la institucion. Con ?status=PENDING
    quedan los que esperan revision."""
    institution = current_institution(request.auth)
    return selectors.projects_of_institution(institution, status=status)


@institution_router.post("/projects", response=ProjectOut)
def create_institution_project(request, payload: ProjectCreateIn):
    """Carga un proyecto en una cursada de la institucion.

    La institucion siempre puede cargar, en cualquiera de sus cursadas: es quien
    habilita a los docentes, asi que nadie tiene que habilitarla a ella. Y como
    es tambien quien revisa, lo que carga nace aprobado y con la revision
    firmada: pedirle que apruebe lo suyo seria un tramite vacio.
    """
    course = academics_selectors.course(payload.course_id)
    ensure_course_of_institution(request.auth, course)

    try:
        project = services.create_project(reviewer=request.auth, **payload.model_dump())
    except ValidationError as exc:
        raise validation_error(exc) from exc

    return selectors.full_project(project.pk)


def _review(request, project_id, status, payload):
    """Las tres decisiones de la revision son el mismo movimiento.

    Cambia el estado con el que se resuelve; lo demas (que el proyecto sea de la
    institucion, guardar quien reviso y cuando, devolver la ficha) es identico,
    asi que se escribe una sola vez.
    """
    project = selectors.project(project_id)
    ensure_project_of_institution(request.auth, project)

    try:
        services.review_project(
            project,
            status=status,
            reviewer=request.auth,
            notes=payload.notes,
        )
    except ValidationError as exc:
        raise validation_error(exc) from exc

    return selectors.full_project(project.pk)


@institution_router.post("/projects/{project_id}/approve", response=ProjectOut)
def approve_project(request, project_id: int, payload: ProjectReviewIn):
    """Publica el proyecto en el catalogo."""
    return _review(request, project_id, ProjectStatus.APPROVED, payload)


@institution_router.post("/projects/{project_id}/request-changes", response=ProjectOut)
def request_changes(request, project_id: int, payload: ProjectReviewIn):
    """Lo devuelve al docente con la devolucion escrita, para que lo corrija."""
    return _review(request, project_id, ProjectStatus.CHANGES, payload)


@institution_router.post("/projects/{project_id}/reject", response=ProjectOut)
def reject_project(request, project_id: int, payload: ProjectReviewIn):
    return _review(request, project_id, ProjectStatus.REJECTED, payload)
