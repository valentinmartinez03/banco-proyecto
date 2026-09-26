from ninja import NinjaAPI

from apps.accounts.api import (
    admin_router as users_admin_router,
    me_router,
    public_router as auth_router,
)


api = NinjaAPI(
    title="Banco de Proyectos API",
    version="1.0.0",
    description=(
        "API del banco de proyectos: instituciones, docentes y los trabajos de sus "
        "cursadas. La institucion habilita a sus docentes; el docente abre sus cursadas, "
        "carga a los alumnos y sube los proyectos de cada equipo con sus imagenes, sus "
        "documentos y sus links. La institucion los aprueba, o le da al docente el "
        "privilegio de publicar sin revision, y lo aprobado se lee en el catalogo publico "
        "sin iniciar sesion. Autenticacion JWT, roles y carga de archivos."
    ),
)


@api.get("/health", tags=["Sistema"])
def healthcheck(request):
    return {"status": "ok"}


# Cada app trae sus routers y este archivo decide bajo que prefijo se cuelgan.
# El prefijo dice a quien le corresponde cada grupo de operaciones:
#   sin prefijo   -> lectura publica y registros, sin token
#   /auth         -> login, refresh y datos de la propia cuenta
#   /teacher      -> lo que hace un docente en sus instituciones
#   /institution  -> la cuenta institucional
#   /admin        -> gestion reservada al administrador
# Que varios routers compartan prefijo no es problema: lo que no se puede
# repetir es la ruta completa.
api.add_router("/auth", auth_router)
api.add_router("/auth", me_router)
api.add_router("/admin", users_admin_router)
