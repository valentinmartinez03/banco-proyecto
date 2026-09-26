from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from apps.accounts.managers import UserManager


class UserRole(models.TextChoices):
    """Tipos de cuenta de la plataforma.

    El dominio tiene dos actores: la institucion y el docente. La institucion
    habilita a sus docentes y revisa lo que suben; el docente carga sus
    cursadas y los proyectos de sus equipos.

    El alumno no es una cuenta. Antes iniciaba sesion y cargaba su propio
    proyecto; ahora es un dato que el docente carga en su cursada
    (academics.Student). Se saco de aca porque en este circuito el alumno nunca
    necesita entrar: quien sube el proyecto, lo corrige y lo vuelve a mandar es
    siempre el docente.

    ADMIN tampoco es un actor del dominio: es la cuenta que administra la
    plataforma, la que entra al admin de Django a cargar tecnologias, dar de
    alta una institucion o destrabar algo. Por eso acompaña a los otros dos en
    todos los permisos.

    TEACHER es un tipo de cuenta, no un permiso general: todo lo que un docente
    puede hacer sale de su membresia aceptada en una institucion
    (InstitutionTeacher), nunca del rol solo.
    """

    ADMIN = "ADMIN", "Administrador"
    INSTITUTION = "INSTITUTION", "Institucion"
    TEACHER = "TEACHER", "Docente"


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True, max_length=255)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    # El default es TEACHER porque el unico alta publica es la del docente
    # (register/teacher). La institucion activa su cuenta con un email que el
    # administrador habilito antes, y el administrador se crea por consola.
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.TEACHER,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["email"]

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email).lower()
        self.is_staff = self.role == UserRole.ADMIN

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()