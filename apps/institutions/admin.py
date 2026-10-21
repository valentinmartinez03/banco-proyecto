from django.contrib import admin

from apps.institutions.models import Institution, InstitutionEmailRule, InstitutionTeacher


class InstitutionEmailRuleInline(admin.TabularInline):
    """Los emails habilitados se cargan aca, junto con la institucion: es la
    configuracion que abre la puerta a la cuenta institucional."""

    model = InstitutionEmailRule
    extra = 1
    readonly_fields = ["user", "created_at"]


@admin.register(Institution)
class InstitutionAdmin(admin.ModelAdmin):
    list_display = ["name", "city", "created_at"]
    search_fields = ["name", "city"]
    inlines = [InstitutionEmailRuleInline]


@admin.register(InstitutionEmailRule)
class InstitutionEmailRuleAdmin(admin.ModelAdmin):
    list_display = ["email", "institution", "user", "created_at"]
    search_fields = ["email", "institution__name"]
    readonly_fields = ["user", "created_at"]


@admin.register(InstitutionTeacher)
class InstitutionTeacherAdmin(admin.ModelAdmin):
    list_display = [
        "teacher",
        "institution",
        "origin",
        "status",
        "publishes_without_review",
        "created_at",
        "responded_at",
    ]
    search_fields = ["teacher__email", "teacher__last_name", "institution__name"]
    list_filter = ["status", "origin", "publishes_without_review"]
    # Se puede tildar desde la lista: es la decision que una institucion cambia
    # mas seguido, y asi no hay que entrar a la ficha de cada docente.
    list_editable = ["publishes_without_review"]
    readonly_fields = ["created_at", "responded_at"]
