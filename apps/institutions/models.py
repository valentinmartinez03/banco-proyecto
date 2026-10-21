from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.institutions.managers import InstitutionQuerySet, InstitutionTeacherQuerySet


class Institution(models.Model):
    """Institucion educativa: la dan de alta los administradores desde el admin.

    Es el actor que organiza casi todo lo demas: los docentes se relacionan con
    ella (InstitutionTeacher), y las carreras, las cursadas y los alumnos que
    el docente carga le pertenecen (app academics). Los proyectos que sube un
    docente esperan su aprobacion: la institucion decide cuales entran al
    catalogo publico.

    No guarda ninguna relacion hacia esas apps: son ellas las que la apuntan.
    Asi las dependencias van en una sola direccion y esta app solo depende de
    accounts.
    """

    name = models.CharField(max_length=180, unique=True)
    city = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = InstitutionQuerySet.as_manager()

    class Meta:
        verbose_name = "institucion"
        verbose_name_plural = "instituciones"
        ordering = ["name"]

    def save(self, *args, **kwargs):
        # Sin esto, dar de alta dos veces la misma institucion revienta contra la
        # restriccion de la base y la API contesta un 500. Con el full_clean, el
        # nombre repetido sale como ValidationError y termina siendo un 400 con
        # el campo adentro, que es lo que el que llama puede corregir.
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class InstitutionEmailRule(models.Model):
    """Email institucional habilitado para manejar la cuenta de una institucion.

    La lista se configura desde el admin de Django: es la llave de entrada de
    las instituciones. Quien tenga un email de esta lista puede activar su
    cuenta (crear su contrasena) y queda a cargo de la institucion a la que la
    regla apunta. Borrar la regla revoca ese acceso sin borrar el usuario.
    """

    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="email_rules",
    )
    email = models.EmailField(unique=True, max_length=255)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="institution_email_rule",
        help_text="Se completa solo, cuando la institucion activa su cuenta.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "email institucional habilitado"
        verbose_name_plural = "emails institucionales habilitados"
        ordering = ["email"]

    def __str__(self):
        return f"{self.email} ({self.institution.name})"

    @property
    def is_activated(self):
        return self.user_id is not None


class MembershipOrigin(models.TextChoices):
    INVITATION = "INVITATION", "Invitacion de la institucion"
    REQUEST = "REQUEST", "Solicitud del docente"


class MembershipStatus(models.TextChoices):
    PENDING = "PENDING", "Pendiente"
    ACCEPTED = "ACCEPTED", "Aceptada"
    REJECTED = "REJECTED", "Rechazada"


class InstitutionTeacher(models.Model):
    """Relacion entre un docente y una institucion.

    El docente no es un rol general de la plataforma: lo que puede hacer sale
    de esta tabla. Sin una membresia aceptada no puede abrir cursadas ni subir
    proyectos en nombre de esta institucion.

    La relacion nace por dos caminos (la institucion invita, o el docente pide
    entrar) y el campo origin recuerda cual fue, porque decide quien tiene que
    responder: una invitacion la responde el docente y una solicitud la
    responde la institucion.

    Aca vive tambien la confianza: publishes_without_review dice si esta
    institucion le cree a este docente sin mirarle los proyectos. Es un campo de
    la relacion y no del usuario porque la confianza no es una propiedad de la
    persona: el mismo docente puede publicar directo en el instituto donde hace
    diez anos que da clase y esperar revision en el que acaba de entrar.
    """

    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        related_name="teacher_memberships",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="institution_memberships",
        verbose_name="docente",
    )
    origin = models.CharField(max_length=12, choices=MembershipOrigin.choices)
    status = models.CharField(
        max_length=10,
        choices=MembershipStatus.choices,
        default=MembershipStatus.PENDING,
    )
    publishes_without_review = models.BooleanField(
        default=False,
        verbose_name="publica sin revision",
        help_text=(
            "Si esta tildado, los proyectos que cargue en esta institucion nacen "
            "aprobados y salen al catalogo sin pasar por la cola de revision."
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    objects = InstitutionTeacherQuerySet.as_manager()

    class Meta:
        verbose_name = "docente de institucion"
        verbose_name_plural = "docentes de instituciones"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["institution", "teacher"],
                name="docente_unico_por_institucion",
            )
        ]

    def __str__(self):
        return f"{self.teacher} en {self.institution} ({self.get_status_display()})"

    @property
    def is_accepted(self):
        return self.status == MembershipStatus.ACCEPTED

    def respond(self, status, save=True):
        """Acepta o rechaza la relacion y deja la fecha de la decision."""
        self.status = status
        self.responded_at = timezone.now()
        if save:
            self.save(update_fields=["status", "responded_at"])
        return self

    def set_publishing_privilege(self, allowed, save=True):
        """Da o saca el permiso de publicar sin revision.

        Sacarlo no baja del catalogo lo que ya se publico: eso ya esta dicho, y
        retirarlo sin avisar seria una correccion silenciosa. Lo que ya no
        corresponda se devuelve con observaciones, que deja constancia escrita.
        """
        self.publishes_without_review = allowed
        if save:
            self.save(update_fields=["publishes_without_review"])
        return self
