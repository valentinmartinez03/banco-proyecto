"""Estructura y comportamiento propio de un proyecto.

Es la app que junta a todas las demas: el proyecto apunta a una cursada
(academics) y de ahi salen la carrera, la institucion y el docente; los alumnos
son los que esa cursada tiene inscriptos, las tecnologias vienen de catalogs y
la revision la firma una cuenta de accounts.

Las relaciones se declaran por nombre ("app.Modelo", settings.AUTH_USER_MODEL) y
no importando la clase: asi las dependencias van en una sola direccion y ninguna
app necesita saber quien la usa.
"""
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.template.defaultfilters import slugify
from django.utils import timezone

from apps.projects.managers import ProjectQuerySet


class ProjectStatus(models.TextChoices):
    PENDING = "PENDING", "Pendiente de aprobacion"
    APPROVED = "APPROVED", "Aprobado"
    CHANGES = "CHANGES", "Con observaciones para corregir"
    REJECTED = "REJECTED", "Rechazado"


class AssetType(models.TextChoices):
    """Que clase de archivo se subio.

    Son dos y no diez a proposito: lo que se sube es lo que ilustra el trabajo
    (capturas, fotos del prototipo) o lo que lo documenta (el informe, la
    presentacion). Todo lo demas es un link y vive en ProjectLink.
    """

    IMAGE = "IMAGE", "Imagen"
    DOCUMENT = "DOCUMENT", "Documento"


class LinkType(models.TextChoices):
    REPOSITORY = "REPOSITORY", "Repositorio"
    DEMO = "DEMO", "Demo publicada"
    VIDEO = "VIDEO", "Video"
    DOCUMENT = "DOCUMENT", "Documento"
    OTHER = "OTHER", "Otro"


def project_asset_upload_to(instance, filename):
    """Arma la ruta donde queda guardado el archivo, dentro de MEDIA_ROOT.

    Una carpeta por proyecto y, adentro, una por tipo: asi la carpeta media se
    puede mirar a ojo y se entiende de quien es cada archivo.
    """
    base_name = Path(filename).name
    return f"projects/{instance.project.slug}/{instance.asset_type.lower()}/{base_name}"


class Project(models.Model):
    """Un trabajo de una cursada, cargado por su docente.

    Quien carga el proyecto es el DOCENTE, no el alumno: el alumno no tiene
    cuenta en la plataforma, es un dato que el docente cargo en la cursada. Por
    eso un mismo docente sube los proyectos de todos los equipos de una misma
    comision, y por eso varios proyectos comparten course. Lo que separa a un
    equipo de otro es team_name, que es un campo del proyecto y no una tabla
    aparte: el equipo no existe fuera del trabajo que hizo.

    No hay clave foranea a la institucion, a la carrera, al docente ni al ciclo
    lectivo: TODAS salen de la cursada, y se exponen como properties
    (institution, career, teacher). No es por escribir menos codigo. Es que el
    dato existe una sola vez: si el proyecto guardara su propia carrera, nada
    impediria que apunte a una carrera distinta de la de su cursada, y habria
    que escribir una validacion para sostener a mano algo que el modelo puede
    hacer imposible. Los filtros pagan el precio de cruzar la relacion
    (course__career__institution) y a cambio el dato no puede contradecirse.

    Nace pendiente: recien cuando la institucion lo aprueba aparece en el
    catalogo publico.
    """

    course = models.ForeignKey(
        "academics.Course",
        on_delete=models.PROTECT,
        related_name="projects",
        verbose_name="cursada",
        help_text="De aca salen la carrera, la institucion, el docente y el ciclo lectivo.",
    )
    team_name = models.CharField(
        max_length=120,
        blank=True,
        verbose_name="equipo",
        help_text="Como se llama el equipo dentro de la cursada, por ejemplo Equipo 3.",
    )
    title = models.CharField(max_length=180, verbose_name="titulo")
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    summary = models.TextField(
        verbose_name="resumen",
        help_text="Las pocas lineas que se leen en el catalogo.",
    )
    description = models.TextField(
        blank=True,
        verbose_name="descripcion",
        help_text="El detalle largo que se lee en la ficha del proyecto.",
    )
    repository_url = models.URLField(
        blank=True,
        verbose_name="repositorio",
        help_text="El repositorio de GitHub del trabajo.",
    )
    status = models.CharField(
        max_length=10,
        choices=ProjectStatus.choices,
        default=ProjectStatus.PENDING,
        verbose_name="estado",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_projects",
        verbose_name="quien lo reviso",
    )
    review_notes = models.TextField(
        blank=True,
        verbose_name="devolucion de la revision",
        help_text="Lo que la institucion le responde al docente: que falta o por que se rechaza.",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="fecha de revision")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProjectQuerySet.as_manager()

    class Meta:
        verbose_name = "proyecto"
        verbose_name_plural = "proyectos"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def career(self):
        """La carrera es la de la cursada: el proyecto no la guarda aparte."""
        return self.course.career

    @property
    def institution(self):
        """Dos saltos, cursada y carrera, para llegar a la institucion.

        Es el mismo criterio que ya usa Course.institution: el dato se responde
        desde donde vive y no se copia.
        """
        return self.course.career.institution

    @property
    def teacher(self):
        """Quien lo cargo es el docente de la cursada, y por eso no hay un campo
        propio que pueda quedar apuntando a otra persona."""
        return self.course.teacher

    @property
    def is_approved(self):
        return self.status == ProjectStatus.APPROVED

    def clean(self):
        """Lo que se puede comprobar mirando solo este proyecto.

        Las reglas que necesitan otras tablas (que los alumnos esten inscriptos
        en la cursada, por ejemplo) no viven aca: se preguntan en el service,
        que es el que tiene el panorama completo y la transaccion abierta.
        """
        super().clean()
        if self.repository_url:
            parsed = urlparse(self.repository_url)
            if parsed.hostname not in {"github.com", "www.github.com"}:
                raise ValidationError({"repository_url": "El repositorio debe pertenecer a GitHub."})

    def review(self, status, *, reviewer=None, notes="", save=True):
        """Guarda la decision de la revision: que se resolvio, quien y cuando.

        La devolucion viaja con la decision porque es parte de ella: un proyecto
        devuelto sin decir que le falta no se puede corregir.
        """
        self.status = status
        self.reviewed_by = reviewer
        self.review_notes = notes
        self.reviewed_at = timezone.now()
        if save:
            self.save(update_fields=["status", "reviewed_by", "review_notes", "reviewed_at"])
        return self

    def _build_unique_slug(self):
        """El slug sale del titulo, y si ya existe se le suma un numero.

        El titulo lo escribe una persona y dos equipos pueden elegir el mismo;
        la direccion publica, en cambio, tiene que ser unica.
        """
        base_slug = slugify(self.title) or "proyecto"
        slug = base_slug
        counter = 2

        while Project.objects.exclude(pk=self.pk).filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        return slug

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._build_unique_slug()
        self.full_clean()
        return super().save(*args, **kwargs)


class ProjectStudent(models.Model):
    """Alumno que hizo el proyecto.

    Apunta a academics.Student, que es un dato de la institucion y no una
    cuenta: el alumno no entra a la plataforma, lo carga el docente cuando arma
    su cursada.

    Las dos puntas no se borran igual. La fila se va con el proyecto
    (on_delete=CASCADE) porque no significa nada fuera de el, pero protege al
    alumno (on_delete=PROTECT): alguien que figura como autor de un trabajo
    publicado no se puede borrar de la institucion sin darse cuenta, porque eso
    dejaria al proyecto sin sus autores.
    """

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="students",
    )
    student = models.ForeignKey(
        "academics.Student",
        on_delete=models.PROTECT,
        related_name="project_participations",
        verbose_name="alumno",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "alumno del proyecto"
        verbose_name_plural = "alumnos del proyecto"
        ordering = ["student__last_name", "student__first_name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "student"],
                name="alumno_unico_por_proyecto",
            )
        ]

    def __str__(self):
        return self.student.full_name


class ProjectTechnology(models.Model):
    """Una tecnologia usada por el proyecto: la tabla del medio, escrita a mano.

    Un proyecto usa varias tecnologias y cada tecnologia aparece en varios
    proyectos. Esa relacion no entra en una columna de ninguna de las dos
    tablas, asi que necesita una tercera con una fila por cada par. Django
    puede crearla sola con un ManyToManyField, pero aca se declara como un
    modelo comun y corriente, con sus dos claves foraneas a la vista.

    La razon es que asi la tabla existe para el proyecto igual que cualquier
    otra: aparece en el DER, se le agregan campos propios el dia que la
    relacion tenga algo que decir de si misma, y se consulta sin depender de
    los atajos que el ManyToManyField esconde.

    Las dos puntas no se borran igual: el par se va con el proyecto
    (on_delete=CASCADE) pero protege a la tecnologia (on_delete=PROTECT), que
    es un catalogo compartido y no se puede borrar mientras describa un
    trabajo.
    """

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="technologies",
    )
    technology = models.ForeignKey(
        "catalogs.Technology",
        on_delete=models.PROTECT,
        related_name="project_technologies",
        verbose_name="tecnologia",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "tecnologia del proyecto"
        verbose_name_plural = "tecnologias del proyecto"
        ordering = ["technology__name"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "technology"],
                name="tecnologia_unica_por_proyecto",
            )
        ]

    def __str__(self):
        return self.technology.name


class ProjectAsset(models.Model):
    """Un archivo del proyecto: lo que se sube y queda guardado en el servidor.

    Es una de las dos mitades de "todo lo relacionado del proyecto". Esta mitad
    es la que la plataforma guarda: las imagenes y los documentos viven en la
    carpeta media y se sirven desde ahi, asi que si manana el equipo borra su
    Drive las capturas siguen estando.

    is_cover marca cual de las imagenes encabeza la ficha. Es un campo del
    archivo y no del proyecto porque la portada es una propiedad de la imagen
    ("esta es la que va arriba"); que haya una sola la sostiene el service, que
    desmarca la anterior cuando se marca una nueva.
    """

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="assets",
    )
    asset_type = models.CharField(
        max_length=10,
        choices=AssetType.choices,
        verbose_name="tipo de archivo",
    )
    title = models.CharField(max_length=120, blank=True, verbose_name="titulo")
    file = models.FileField(upload_to=project_asset_upload_to, verbose_name="archivo")
    is_cover = models.BooleanField(
        default=False,
        verbose_name="portada",
        help_text="La imagen que encabeza la ficha del proyecto.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "archivo del proyecto"
        verbose_name_plural = "archivos del proyecto"
        ordering = ["-is_cover", "created_at"]

    def __str__(self):
        return f"{self.project.title} - {self.get_asset_type_display()}"


class ProjectLink(models.Model):
    """Un link del proyecto: lo que vive afuera de la plataforma.

    Es la otra mitad de "todo lo relacionado del proyecto". El repositorio de
    GitHub, la demo publicada, el video de la defensa: nada de eso se sube, ya
    esta en algun lado y lo unico que hace falta es guardar donde.

    repository_url sigue siendo un campo de Project y no una fila de aca porque
    es el link que siempre se pide: es parte de la ficha, no un agregado. Esta
    tabla guarda todos los demas, que son cuantos haga falta, y esa es la razon
    de que sea una tabla: la cantidad no se sabe de antemano.

    La url es unica dentro del proyecto para que cargar dos veces el mismo link
    no ensucie la ficha.
    """

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="links",
    )
    link_type = models.CharField(
        max_length=12,
        choices=LinkType.choices,
        verbose_name="tipo de link",
    )
    title = models.CharField(max_length=120, blank=True, verbose_name="titulo")
    url = models.URLField(verbose_name="direccion")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "link del proyecto"
        verbose_name_plural = "links del proyecto"
        ordering = ["link_type", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "url"],
                name="link_unico_por_proyecto",
            )
        ]

    def __str__(self):
        return self.title or self.url
