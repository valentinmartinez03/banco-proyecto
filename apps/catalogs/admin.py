from django.contrib import admin

from apps.catalogs.models import Technology


@admin.register(Technology)
class TechnologyAdmin(admin.ModelAdmin):
    """El admin ES la forma de cargar tecnologias: no hay endpoint de alta.

    Con una lista buscable alcanza, porque el modelo tiene un solo campo que se
    escribe. Buscar antes de crear es lo que evita que entre "React" dos veces
    con mayusculas distintas.
    """

    list_display = ["name", "created_at"]
    search_fields = ["name"]
from django.contrib import admin

# Register your models here.
