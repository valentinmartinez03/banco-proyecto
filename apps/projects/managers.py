"""Filtros reutilizables del catalogo de proyectos."""
from django.db import models


class ProjectQuerySet(models.QuerySet):
    """Cada metodo hace una sola cosa y devuelve otro queryset, asi se encadenan:
    Project.objects.approved().of_year(2026).with_student("ana").

    Que vivan aca y no sueltos en la API tiene tres consecuencias practicas:
    "aprobado" se define una sola vez, los mismos filtros sirven para el
    catalogo publico, para la lista del docente y para la bandeja de la
    institucion, y nada de esto se repite el dia que haya que agregar un filtro
    nuevo.

    Casi todos los filtros cruzan la cursada, porque el proyecto no guarda ni la
    carrera ni la institucion ni el docente: los tiene una sola vez, en course.
    El doble guion bajo sigue la relacion hasta donde el dato vive de verdad.
    """

    def approved(self):
        # El import va aca adentro y no arriba: models.py importa este archivo,
        # y que los dos se importen arriba seria un import circular.
        from apps.projects.models import ProjectStatus

        return self.filter(status=ProjectStatus.APPROVED)

    def of_teacher(self, user):
        # Los proyectos de un docente son los de sus cursadas: quien carga el
        # proyecto es siempre el docente que dicta esa comision.
        return self.filter(course__teacher=user)

    def of_course(self, course_id):
        return self.filter(course_id=course_id)

    def search(self, text):
        return self.filter(
            models.Q(title__icontains=text) | models.Q(summary__icontains=text)
        )

    def with_student(self, name):
        # Cruza una relacion de a muchos: sin distinct(), un proyecto de equipo
        # aparece una vez por cada alumno que coincide.
        return self.filter(
            models.Q(students__student__first_name__icontains=name)
            | models.Q(students__student__last_name__icontains=name)
        ).distinct()

    def with_technology(self, technology_id):
        # technologies son las filas de la tabla del medio, asi que el filtro
        # cruza dos relaciones: de proyecto a ProjectTechnology y de ahi a la
        # tecnologia.
        return self.filter(technologies__technology_id=technology_id).distinct()

    def of_institution(self, institution):
        # Acepta la institucion o su id: la bandeja pasa el objeto que ya tiene
        # y el catalogo publico, el id que vino en la URL.
        return self.filter(course__career__institution=institution)

    def of_career(self, career_id):
        return self.filter(course__career_id=career_id)

    def of_year(self, year):
        # El ciclo lectivo es un campo de la cursada: no hay catalogo de anios
        # ni una tabla que mantener al dia.
        return self.filter(course__year=year)

    def of_team(self, text):
        return self.filter(team_name__icontains=text)

    def with_related(self):
        """Trae en pocas consultas todo lo que necesita la ficha completa.

        Sin esto, cada proyecto de la lista dispararia consultas extra: es el
        problema N+1. Como la carrera, la institucion y el docente se responden
        cruzando la cursada, el select_related tiene que traer esa cadena
        entera; si no, preguntar por project.institution en el template o en el
        schema seria una consulta por proyecto.

        select_related sirve para las relaciones de a uno y prefetch_related
        para las de a muchos, sin importar en que app viva cada modelo del
        camino.
        """
        return self.select_related(
            "course",
            "course__career",
            "course__career__institution",
            "course__teacher",
            "reviewed_by",
        ).prefetch_related(
            "technologies__technology",
            "students__student",
            "assets",
            "links",
        )
