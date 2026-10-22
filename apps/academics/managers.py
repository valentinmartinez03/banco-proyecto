"""Filtros encadenables de carreras, cursadas, alumnos e inscripciones.

Cada filtro es una pregunta escrita una sola vez. Los selectors los combinan y
asi nadie vuelve a escribir a mano el camino career__institution.
"""
from django.db import models


class CareerQuerySet(models.QuerySet):
    """Filtros de carreras."""

    def of_institution(self, institution):
        return self.filter(institution=institution)

    def search(self, text):
        return self.filter(name__icontains=text)

    def with_institution(self):
        return self.select_related("institution")


class CourseQuerySet(models.QuerySet):
    """Filtros de cursadas."""

    def of_teacher(self, teacher):
        return self.filter(teacher=teacher)

    def of_institution(self, institution):
        """La cursada no guarda la institucion: se llega por la carrera.

        El camino esta escrito aca y no en cada selector, asi el dia que la
        relacion cambie hay un solo lugar que tocar.
        """
        return self.filter(career__institution=institution)

    def with_related(self):
        return self.select_related("career__institution", "teacher")


class StudentQuerySet(models.QuerySet):
    """Filtros de alumnos."""

    def of_institution(self, institution):
        return self.filter(institution=institution)

    def with_email(self, email):
        """Busca por email sin distinguir mayusculas.

        Es la pregunta que decide si el alumno ya existe cuando el docente lo
        carga: "ana@alumnos.edu.ar" y "Ana@Alumnos.edu.ar" son la misma persona.
        """
        return self.filter(email__iexact=email)


class CourseStudentQuerySet(models.QuerySet):
    """Filtros de inscripciones."""

    def of_course(self, course):
        return self.filter(course=course)

    def with_student(self):
        return self.select_related("student")
