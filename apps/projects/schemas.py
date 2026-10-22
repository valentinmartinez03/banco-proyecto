"""La forma de lo que entra y de lo que sale por HTTP.

Los schemas de salida reusan los de las otras apps en vez de repetir sus campos:
si manana la institucion suma un dato, aparece solo. Es la misma direccion de
dependencia que en los modelos: proyectos conoce a las demas y no al reves.
"""
from datetime import datetime
from typing import Optional

from ninja import Schema

from apps.academics.schemas import CareerOut, CourseOut
from apps.catalogs.schemas import TechnologyOut
from apps.institutions.schemas import InstitutionOut


class ProjectFilters(Schema):
    """Filtros del catalogo. Todos son opcionales y se combinan entre si.

    institution_id, career_id, course_id y year no son campos del proyecto: son
    datos de la cursada, y por eso el queryset los busca cruzando la relacion.
    Para el que consulta la API eso es invisible, que es como tiene que ser.
    """

    search: Optional[str] = None
    student: Optional[str] = None
    institution_id: Optional[int] = None
    career_id: Optional[int] = None
    course_id: Optional[int] = None
    technology_id: Optional[int] = None
    year: Optional[int] = None
    team: Optional[str] = None


class ProjectCreateIn(Schema):
    """Lo que manda el docente para cargar un proyecto.

    No pide institucion ni carrera ni docente: con la cursada alcanza, porque de
    ella salen los tres. Un formulario con menos campos es tambien un formulario
    con menos maneras de equivocarse.
    """

    course_id: int
    team_name: str = ""
    title: str
    summary: str
    description: str = ""
    repository_url: str = ""
    technology_ids: list[int] = []
    # Ids de alumnos de academics. Tienen que estar inscriptos en la cursada.
    student_ids: list[int] = []


class ProjectUpdateIn(Schema):
    """Todos los campos son opcionales: se manda solo lo que se corrige.

    Si technology_ids o student_ids llegan, reemplazan la lista completa. No hay
    course_id: un proyecto no cambia de cursada.
    """

    team_name: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None
    repository_url: Optional[str] = None
    technology_ids: Optional[list[int]] = None
    student_ids: Optional[list[int]] = None


class ProjectReviewIn(Schema):
    """Lo que manda la institucion cuando revisa.

    Es un solo campo: la devolucion escrita. La decision (aprobar, devolver o
    rechazar) no viaja en el cuerpo, esta en el endpoint que se llamo.
    """

    notes: str = ""


class ProjectLinkIn(Schema):
    link_type: str
    title: str = ""
    url: str


class ProjectLinkOut(Schema):
    id: int
    link_type: str
    link_type_label: str
    title: str
    url: str
    created_at: datetime

    @staticmethod
    def resolve_link_type_label(obj):
        # get_FOO_display() devuelve la etiqueta legible de un campo con
        # choices: el cliente no tiene que conocer las constantes para mostrar
        # "Demo publicada".
        return obj.get_link_type_display()


class ProjectAssetOut(Schema):
    id: int
    asset_type: str
    asset_type_label: str
    title: str
    file_url: str
    is_cover: bool
    created_at: datetime

    @staticmethod
    def resolve_asset_type_label(obj):
        return obj.get_asset_type_display()

    @staticmethod
    def resolve_file_url(obj, context):
        # El cliente necesita una URL completa para poner en un <img>, no la
        # ruta interna donde quedo guardado el archivo.
        request = context["request"]
        return request.build_absolute_uri(obj.file.url)


class ProjectParticipantOut(Schema):
    """Los alumnos que hicieron el proyecto.

    Salen del Student de academics, que es un dato de la institucion: nombre y
    mail, nada mas. No hay perfil ni presentacion porque el alumno no tiene
    cuenta en la plataforma y nunca escribio nada sobre si mismo.
    """

    id: int
    full_name: str
    email: str

    @staticmethod
    def resolve_id(obj):
        # obj es la fila de ProjectStudent; el id que le sirve al cliente es el
        # del alumno, no el del par.
        return obj.student_id

    @staticmethod
    def resolve_full_name(obj):
        return obj.student.full_name

    @staticmethod
    def resolve_email(obj):
        return obj.student.email


class ProjectSummaryOut(Schema):
    """La version corta, para las listas.

    El catalogo muestra decenas de proyectos y ninguno necesita ahi su
    descripcion completa ni sus links: con el titulo, el equipo, el resumen y la
    portada alcanza para decidir en cual entrar. La ficha entera se pide despues,
    de a uno, con ProjectOut.
    """

    id: int
    title: str
    slug: str
    team_name: str
    summary: str
    status: str
    status_label: str
    institution_name: str
    career_name: str
    course_name: str
    year: int
    technologies: list[TechnologyOut]
    cover_url: Optional[str] = None

    @staticmethod
    def resolve_status_label(obj):
        return obj.get_status_display()

    @staticmethod
    def resolve_institution_name(obj):
        return obj.institution.name

    @staticmethod
    def resolve_career_name(obj):
        return obj.career.name

    @staticmethod
    def resolve_course_name(obj):
        return obj.course.name

    @staticmethod
    def resolve_year(obj):
        return obj.course.year

    @staticmethod
    def resolve_technologies(obj):
        return [row.technology for row in obj.technologies.all()]

    @staticmethod
    def resolve_cover_url(obj, context):
        # Se recorre lo que ya vino prefetcheado en vez de preguntar a la base
        # por la portada: una consulta mas por proyecto es justo lo que
        # with_related() vino a evitar.
        for asset in obj.assets.all():
            if asset.is_cover:
                return context["request"].build_absolute_uri(asset.file.url)
        return None


class ProjectOut(Schema):
    """La ficha completa.

    institution, career y teacher_name no son campos del modelo: son properties
    que responden desde la cursada. La respuesta los muestra igual, porque el
    que consume la API no tiene por que saber en que tabla esta guardado cada
    dato.
    """

    id: int
    title: str
    slug: str
    team_name: str
    summary: str
    description: str
    repository_url: str
    status: str
    status_label: str
    review_notes: str
    course: CourseOut
    career: CareerOut
    institution: InstitutionOut
    teacher_name: str
    students: list[ProjectParticipantOut]
    technologies: list[TechnologyOut]
    assets: list[ProjectAssetOut]
    links: list[ProjectLinkOut]
    reviewed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Los campos que no salen tal cual del modelo se resuelven aca. Asi la forma
    # de la respuesta se declara en un solo lugar y los endpoints devuelven el
    # objeto del ORM sin armar diccionarios a mano.
    @staticmethod
    def resolve_status_label(obj):
        return obj.get_status_display()

    @staticmethod
    def resolve_teacher_name(obj):
        return obj.teacher.full_name

    @staticmethod
    def resolve_students(obj):
        return list(obj.students.all())

    @staticmethod
    def resolve_technologies(obj):
        # obj.technologies son las filas de la tabla del medio; la respuesta
        # muestra la tecnologia de cada una, no el par. La forma de la API no
        # cambia porque el modelo de datos haya cambiado.
        return [row.technology for row in obj.technologies.all()]

    @staticmethod
    def resolve_assets(obj):
        return list(obj.assets.all())

    @staticmethod
    def resolve_links(obj):
        return list(obj.links.all())
