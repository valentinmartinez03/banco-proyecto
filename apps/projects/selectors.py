"""Consultas de lectura de proyectos.

El buscador es el mejor ejemplo de para que sirve esta capa: los filtros sueltos
son del queryset, pero "aplicar los filtros que mando el cliente, en este orden,
sobre estos proyectos" es una decision de lectura y vive aca. La API solo pasa
los datos que recibio.
"""
from django.shortcuts import get_object_or_404

from apps.projects.models import Project, ProjectAsset, ProjectLink


def _apply_filters(queryset, filters):
    """Suma condiciones solo por los filtros que vinieron con valor.

    Como cada metodo del queryset devuelve otro queryset, los filtros se
    combinan solos y con AND: pedir tecnologia y anio deja los proyectos que
    cumplen las dos cosas, sin escribir una consulta por combinacion posible.
    """
    if filters.search:
        queryset = queryset.search(filters.search)
    if filters.student:
        queryset = queryset.with_student(filters.student)
    if filters.team:
        queryset = queryset.of_team(filters.team)
    if filters.institution_id:
        queryset = queryset.of_institution(filters.institution_id)
    if filters.career_id:
        queryset = queryset.of_career(filters.career_id)
    if filters.course_id:
        queryset = queryset.of_course(filters.course_id)
    if filters.technology_id:
        queryset = queryset.with_technology(filters.technology_id)
    if filters.year:
        queryset = queryset.of_year(filters.year)
    return queryset


def public_catalog(filters):
    """Lo que ve cualquiera: solo los proyectos aprobados por su institucion."""
    return _apply_filters(Project.objects.approved().with_related(), filters)


def approved_project(slug):
    """La ficha publica.

    Se busca entre los aprobados y no entre todos: si se buscara el proyecto y
    despues se preguntara por su estado, un pendiente responderia 403 en vez de
    404 y eso ya cuenta que existe.
    """
    return get_object_or_404(Project.objects.approved().with_related(), slug=slug)


def project(project_id):
    """El proyecto para decidir permisos y para operar sobre el.

    Trae la cadena hasta la institucion porque es lo que necesitan las dos
    comprobaciones de la API (de que docente es la cursada, de que institucion
    es la carrera): asi se resuelven con la misma consulta y no con tres.
    """
    return get_object_or_404(
        Project.objects.select_related("course__career__institution", "course__teacher"),
        pk=project_id,
    )


def full_project(project_id):
    """El mismo proyecto pero con todo lo que necesita la respuesta.

    Se usa despues de crear, editar o revisar: la escritura devuelve el objeto y
    la lectura lo vuelve a traer con sus relaciones, sin repetir consultas
    sueltas en el schema.
    """
    return Project.objects.with_related().get(pk=project_id)


def projects_of_teacher(teacher, filters):
    """Los proyectos de las cursadas del docente, con los mismos filtros que el
    catalogo y sin importar su estado: el docente tiene que ver lo pendiente y
    lo devuelto, que es lo que todavia le queda por hacer."""
    return _apply_filters(Project.objects.of_teacher(teacher).with_related(), filters)


def projects_of_institution(institution, status=None):
    """La bandeja de la institucion: los proyectos de sus carreras,
    opcionalmente por estado (con status=PENDING quedan los que esperan
    revision)."""
    queryset = Project.objects.of_institution(institution).with_related()
    if status:
        queryset = queryset.filter(status=status.upper())
    return queryset


def asset(project, asset_id):
    """Un archivo del proyecto.

    Pide los dos ids juntos para que no se pueda borrar el archivo de otro
    proyecto pasando el id suelto: el permiso se comprobo sobre el proyecto, asi
    que la consulta tiene que quedar encerrada en el.
    """
    return get_object_or_404(ProjectAsset, pk=asset_id, project=project)


def link(project, link_id):
    """Un link del proyecto, encerrado en el por la misma razon que el archivo."""
    return get_object_or_404(ProjectLink, pk=link_id, project=project)
