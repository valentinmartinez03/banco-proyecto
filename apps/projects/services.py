"""Operaciones que modifican proyectos: aca viven las reglas.

Es la capa del "y ademas": crear un proyecto no es insertar una fila, es
comprobar que los alumnos sean de esa cursada, insertar el proyecto, cargar sus
tecnologias y cargar sus alumnos, todo o nada. Nada de eso es responsabilidad de
un endpoint ni de un modelo suelto.

Cuando algo no cumple una regla, la funcion levanta un ValidationError de
Django: el service no sabe que existe HTTP. Traducirlo a un 400 es tarea de la
API, con core.errors.validation_error.
"""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.academics import selectors as academics_selectors
from apps.catalogs import selectors as catalogs_selectors
from apps.institutions import selectors as institutions_selectors
from apps.projects.models import (
    AssetType,
    LinkType,
    Project,
    ProjectAsset,
    ProjectLink,
    ProjectStatus,
    ProjectStudent,
    ProjectTechnology,
)


def _students_of_course(course, student_ids):
    """Resuelve los alumnos del proyecto y controla que sean de esa cursada.

    Es la regla que sostiene todo el circuito: un proyecto de la comision de la
    noche no puede tener como autor a alguien que nunca curso ahi. La pregunta
    no se hace consultando las tablas de academics de prepo, se le pide a la app
    duena del dato con students_enrolled_in_course, que devuelve solo los que
    estan inscriptos. Si faltan, es que alguno de los ids no lo esta.
    """
    ids = list(dict.fromkeys(student_ids or []))
    if not ids:
        raise ValidationError({"student_ids": "Hay que cargar al menos un alumno."})

    students = list(academics_selectors.students_enrolled_in_course(course, ids))
    if len(students) != len(ids):
        raise ValidationError(
            {"student_ids": "Algun alumno no esta inscripto en la cursada del proyecto."}
        )
    return students


def replace_students(project, students):
    """Deja la lista de alumnos igual a la que llego: borra las filas viejas e
    inserta las nuevas."""
    project.students.all().delete()
    ProjectStudent.objects.bulk_create(
        [ProjectStudent(project=project, student=student) for student in students]
    )


def replace_technologies(project, technology_ids):
    """Deja la lista de tecnologias igual a la que llego.

    Como la relacion se guarda en una tabla propia (ProjectTechnology), cambiar
    las tecnologias es borrar las filas viejas e insertar las nuevas: lo mismo
    que se hace con los alumnos. No hay atajo que lo haga por nosotros, y eso es
    justamente lo que deja la operacion a la vista.
    """
    project.technologies.all().delete()
    ProjectTechnology.objects.bulk_create(
        [
            ProjectTechnology(
                project=project,
                technology=catalogs_selectors.technology(technology_id),
            )
            for technology_id in dict.fromkeys(technology_ids or [])
        ]
    )


def _initial_status(course):
    """Con que estado nace, o vuelve a nacer, un proyecto de esta cursada.

    Pendiente es lo normal: lo publica la aprobacion de la institucion y no el
    docente que lo sube. La excepcion es el docente al que su institucion le dio
    el privilegio de publicar sin revision, y entonces el proyecto sale
    aprobado derecho.

    La pregunta se hace cada vez, y no se guarda en el proyecto: si manana la
    institucion le saca el privilegio al docente, la proxima edicion ya vuelve a
    la cola de revision sin que haya que tocar nada de lo viejo.
    """
    trusted = institutions_selectors.teacher_publishes_without_review(
        course.teacher, course.career.institution
    )
    return ProjectStatus.APPROVED if trusted else ProjectStatus.PENDING


@transaction.atomic
def create_project(*, course_id, student_ids, technology_ids, reviewer=None, **data):
    """Carga un proyecto de una cursada: todo junto o nada.

    Los alumnos se comprueban ANTES de insertar nada, pero igual hace falta la
    transaccion: las tecnologias y los alumnos son filas de otras dos tablas que
    se insertan despues del proyecto, y si algo falla en el medio no puede
    quedar un proyecto a medio crear. @transaction.atomic es lo que garantiza
    que la base vuelva a como estaba.

    El proyecto nace PENDING: lo publica la aprobacion de la institucion, no el
    docente que lo sube. Salvo que la institucion le haya dado a ese docente el
    privilegio de publicar sin revision, y ahi nace aprobado (_initial_status).
    Queda sin reviewed_by, que es justamente lo que distingue despues un
    proyecto que la institucion miro de uno que publico por confianza.

    `reviewer` es la institucion, cuando es ella la que carga. Ese proyecto nace
    aprobado y con la revision firmada por quien lo cargo: la institucion es la
    que revisa, y no tiene sentido que se apruebe a si misma.
    """
    course = academics_selectors.course(course_id)
    students = _students_of_course(course, student_ids)

    project = Project(course=course, status=_initial_status(course), **data)
    if reviewer is not None:
        project.review(ProjectStatus.APPROVED, reviewer=reviewer, save=False)
    project.save()
    replace_technologies(project, technology_ids)
    replace_students(project, students)
    return project


@transaction.atomic
def update_project(project, *, changes):
    """Aplica solo lo que vino y vuelve el proyecto a la cola de revision.

    Editar un proyecto lo devuelve a PENDING: lo que esta publicado tiene que
    ser siempre una version que la institucion vio. Se limpian quien reviso y
    cuando, porque esa revision ya no corresponde a este texto. Al docente con
    privilegio no lo devuelve a la cola, por el mismo motivo por el que no lo
    hizo al crearlo: su edicion tambien sale publicada.

    La devolucion escrita (review_notes), en cambio, NO se borra: el docente la
    sigue teniendo a la vista mientras corrige, que es justamente para lo que se
    la escribieron. Se reemplaza sola en la proxima revision.

    La cursada no esta entre los campos editables. Cambiarla cambiaria de golpe
    la institucion, la carrera y el docente del proyecto, y dejaria adentro
    alumnos de otra comision: si un trabajo se cargo en la cursada equivocada,
    se carga de nuevo donde va.
    """
    technology_ids = changes.pop("technology_ids", None)
    student_ids = changes.pop("student_ids", None)

    for field, value in changes.items():
        setattr(project, field, value)

    project.status = _initial_status(project.course)
    project.reviewed_by = None
    project.reviewed_at = None
    project.save()

    if technology_ids is not None:
        replace_technologies(project, technology_ids)
    if student_ids is not None:
        replace_students(project, _students_of_course(project.course, student_ids))
    return project


def review_project(project, *, status, reviewer=None, notes=""):
    """La revision de la institucion: aprueba, devuelve con observaciones o rechaza.

    Devolver con observaciones es lo que separa a esto de un boton de si o no:
    el proyecto vuelve al docente con una devolucion escrita, en vez de quedar
    rechazado sin camino de vuelta. Por eso, para devolver o rechazar, la
    devolucion es obligatoria: sin decir que falta, el trabajo no se puede
    corregir.
    """
    if status not in {ProjectStatus.APPROVED, ProjectStatus.CHANGES, ProjectStatus.REJECTED}:
        raise ValidationError({"status": "Estado invalido: se aprueba, se devuelve o se rechaza."})
    if status != ProjectStatus.APPROVED and not notes.strip():
        raise ValidationError(
            {"notes": "Para devolver o rechazar un proyecto hay que escribir la devolucion."}
        )

    return project.review(status, reviewer=reviewer, notes=notes)


@transaction.atomic
def upload_asset(project, *, asset_type, title, file, is_cover=False):
    """Guarda una imagen o un documento del proyecto.

    El archivo llega con su content_type declarado por el navegador y se
    comprueba que se corresponda con el tipo que dice ser: sin esto, un video de
    300 MB entraria como "imagen" y la ficha mostraria un recuadro roto.

    Marcar la portada es una operacion de dos pasos (desmarcar la anterior y
    marcar esta) y por eso la funcion es atomica: no puede quedar un proyecto
    con dos portadas ni con ninguna.
    """
    if asset_type not in AssetType.values:
        raise ValidationError(
            {"asset_type": f"Tipo de archivo invalido. Opciones: {', '.join(AssetType.values)}."}
        )

    content_type = getattr(file, "content_type", "") or ""
    if asset_type == AssetType.IMAGE and not content_type.startswith("image/"):
        raise ValidationError({"file": "Para IMAGE se espera un archivo de imagen."})
    if asset_type == AssetType.DOCUMENT and not content_type.startswith(("application/", "text/")):
        raise ValidationError({"file": "Para DOCUMENT se espera un documento."})

    if is_cover:
        project.assets.filter(is_cover=True).update(is_cover=False)

    return ProjectAsset.objects.create(
        project=project,
        asset_type=asset_type,
        title=title,
        file=file,
        is_cover=is_cover,
    )


def delete_asset(asset):
    """Borra el archivo del disco y despues la fila.

    En ese orden: si se borrara primero la fila, nadie sabria despues que
    archivo de la carpeta media hay que borrar y quedaria basura para siempre.
    """
    asset.file.delete(save=False)
    asset.delete()


def add_link(project, *, link_type, title, url):
    """Suma un link al proyecto.

    La url no se puede repetir dentro del mismo proyecto. La base ya lo impide
    con una restriccion, pero se pregunta igual aca para responder un error de
    negocio entendible en vez de que la insercion explote contra la restriccion.
    """
    if link_type not in LinkType.values:
        raise ValidationError(
            {"link_type": f"Tipo de link invalido. Opciones: {', '.join(LinkType.values)}."}
        )
    if project.links.filter(url=url).exists():
        raise ValidationError({"url": "Ese link ya esta cargado en el proyecto."})

    return ProjectLink.objects.create(
        project=project,
        link_type=link_type,
        title=title,
        url=url,
    )


def delete_link(link):
    link.delete()
