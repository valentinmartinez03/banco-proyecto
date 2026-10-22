from datetime import datetime

from ninja import Schema


class CareerIn(Schema):
    name: str


class CareerOut(Schema):
    id: int
    name: str
    institution_id: int
    institution_name: str

    @staticmethod
    def resolve_institution_name(obj):
        return obj.institution.name


class CourseIn(Schema):
    """Lo que manda el docente para abrir una cursada.

    El ciclo lectivo son dos campos sueltos y no el id de otra tabla: year es el
    ano y term una de las opciones de CourseTerm.
    """

    career_id: int
    name: str
    year: int
    term: str


class CourseOut(Schema):
    id: int
    name: str
    year: int
    term: str
    term_label: str
    career: CareerOut
    teacher_name: str

    @staticmethod
    def resolve_term_label(obj):
        """El texto legible sale del modelo y no se reescribe en el front."""
        return obj.get_term_display()

    @staticmethod
    def resolve_teacher_name(obj):
        return obj.teacher.full_name


class StudentOut(Schema):
    id: int
    first_name: str
    last_name: str
    full_name: str
    email: str


class EnrollStudentIn(Schema):
    """Lo que carga el docente para sumar un alumno a su cursada.

    No hay contrasena ni cuenta: el alumno no entra a la plataforma. El email es
    opcional, pero es lo unico que permite reconocerlo si ya fue cargado en otra
    cursada de la misma institucion.
    """

    first_name: str
    last_name: str
    email: str = ""


class EnrollmentOut(Schema):
    id: int
    student: StudentOut
    created_at: datetime
