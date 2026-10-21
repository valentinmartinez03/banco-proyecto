from ninja import Router

from apps.catalogs import selectors
from apps.catalogs.schemas import TechnologyOut


# Lectura publica, sin token: esta lista alimenta el filtro por tecnologia del
# catalogo de proyectos, que cualquiera puede mirar sin tener cuenta. No hay
# router privado porque el alta y la baja se hacen desde el admin.
public_router = Router(tags=["Catalogos"])


@public_router.get("/technologies", response=list[TechnologyOut])
def list_technologies(request, search: str = None):
    """Las tecnologias cargadas, opcionalmente filtradas por nombre."""
    return selectors.technologies(search=search)
