"""El proyecto en el admin de Django.

El admin es la puerta de servicio: sirve para mirar y arreglar datos, no para
reemplazar a la API. Por eso lo unico que se configura aca es lo que hace falta
para encontrar un proyecto y ver sus tablas relacionadas.
"""
from django.contrib import admin

from apps.projects.models import (
    Project,
    ProjectAsset,
    ProjectLink,
    ProjectStudent,
    ProjectTechnology,
)


class ProjectStudentInline(admin.TabularInline):
    model = ProjectStudent
    extra = 1


class ProjectTechnologyInline(admin.TabularInline):
    # Al no haber ManyToManyField no hay widget de doble lista: las tecnologias
    # se cargan como filas, que es lo que son.
    model = ProjectTechnology
    extra = 1


class ProjectAssetInline(admin.TabularInline):
    model = ProjectAsset
    extra = 0


class ProjectLinkInline(admin.TabularInline):
    model = ProjectLink
    extra = 0


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["title", "team_name", "course", "institution", "status", "created_at"]
    # Buscar por alumno, por carrera o por institucion cruza tablas, y en casi
    # todos los casos cruza tambien de app: eso es lo que hace el doble guion
    # bajo, seguir la relacion hasta el campo del otro modelo. Como el proyecto
    # no guarda la institucion, el camino arranca siempre por la cursada.
    search_fields = [
        "title",
        "team_name",
        "course__name",
        "course__career__name",
        "course__career__institution__name",
        "students__student__first_name",
        "students__student__last_name",
    ]
    list_filter = ["status", "course__year", "course__term", "course__career__institution"]
    prepopulated_fields = {"slug": ("title",)}
    inlines = [
        ProjectStudentInline,
        ProjectTechnologyInline,
        ProjectAssetInline,
        ProjectLinkInline,
    ]

    def get_search_results(self, request, queryset, search_term):
        # Al buscar por alumno, un proyecto de equipo apareceria una vez por
        # alumno que coincide; distinct() lo deja en una sola fila.
        queryset, _ = super().get_search_results(request, queryset, search_term)
        return queryset.distinct(), False


@admin.register(ProjectAsset)
class ProjectAssetAdmin(admin.ModelAdmin):
    list_display = ["project", "asset_type", "title", "is_cover", "created_at"]
    search_fields = ["project__title", "title"]
    list_filter = ["asset_type", "is_cover"]


@admin.register(ProjectLink)
class ProjectLinkAdmin(admin.ModelAdmin):
    list_display = ["project", "link_type", "title", "url", "created_at"]
    search_fields = ["project__title", "title", "url"]
    list_filter = ["link_type"]
