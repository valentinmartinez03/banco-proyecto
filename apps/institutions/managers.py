from django.db import models


class InstitutionQuerySet(models.QuerySet):
    """Filtros de instituciones."""

    def search(self, text):
        return self.filter(name__icontains=text)


class InstitutionTeacherQuerySet(models.QuerySet):
    """Filtros de la relacion docente-institucion.

    Que "docente aceptado" signifique status=ACCEPTED se escribe una sola vez,
    aca. Toda pregunta del estilo "puede este docente tocar esta cursada" pasa
    por estos metodos.
    """

    def accepted(self):
        # El import va aca adentro y no arriba: models.py importa este archivo,
        # y que los dos se importen arriba seria un import circular.
        from apps.institutions.models import MembershipStatus

        return self.filter(status=MembershipStatus.ACCEPTED)

    def of_institution(self, institution):
        return self.filter(institution=institution)

    def of_teacher(self, teacher):
        return self.filter(teacher=teacher)

    def with_related(self):
        return self.select_related("institution", "teacher")
