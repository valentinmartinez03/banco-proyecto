from django.db import models


class Technology(models.Model):
    """Tecnologia usada por un proyecto: Python, Django, React, PostgreSQL.

    Es el unico catalogo que quedo en la plataforma y por eso ya no hereda de
    una base abstracta: cuando habia cinco catalogos identicos valia la pena
    escribir la forma una sola vez, con uno solo esa base solo agregaba una
    clase mas para leer.

    Existe como tabla propia y no como un texto libre dentro del proyecto
    porque los nombres tienen que coincidir: si cada docente escribe la
    tecnologia a mano, el catalogo publico termina con "React", "react" y
    "ReactJS" como si fueran tres cosas distintas, y el filtro deja de servir.
    Una fila por tecnologia significa un nombre unico al que todos apuntan.

    Es tambien lo que le da sentido a ProjectTechnology, la tabla del medio que
    projects escribe a mano en vez de usar un ManyToManyField: un proyecto usa
    varias tecnologias y una tecnologia aparece en varios proyectos. Desde ahi
    la relacion apunta a esta tabla con on_delete=PROTECT, asi que una
    tecnologia no se puede borrar mientras algun proyecto la este usando; es un
    catalogo compartido, no un dato de un proyecto en particular.

    El alta y la baja se hacen desde el admin de Django: por eso esta app no
    tiene services.py.
    """

    name = models.CharField(max_length=120, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "tecnologia"
        verbose_name_plural = "tecnologias"

    def __str__(self):
        return self.name
