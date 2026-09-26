"""Permisos listos para usar en los routers de la API.

Estan en un solo lugar para que la respuesta a "quien puede hacer esto" no
quede desparramada por los endpoints. Cada router de la API elige uno de estos
y no vuelve a preguntar por el rol adentro de las funciones.

El dominio tiene dos actores, la institucion y el docente, y el administrador
los acompana a los dos: puede hacer todo lo que hace cualquiera de ellos. Lo
que un rol NO alcanza a responder (por ejemplo, si un docente pertenece a la
institucion que quiere tocar, o si un proyecto es de una de sus cursadas) se
pregunta despues, a nivel de objeto, en la capa que corresponda.
"""
from apps.accounts.models import UserRole
from core.auth import JWTAuth, RoleAuth


# Cualquier usuario con un token de acceso valido, sin importar el rol.
authenticated = JWTAuth()

# Solo administradores: gestion de usuarios y alta de instituciones.
admin_only = RoleAuth(UserRole.ADMIN)

# Cuentas institucionales: docentes, carreras, cursadas y revision de proyectos.
institution_or_admin = RoleAuth(UserRole.ADMIN, UserRole.INSTITUTION)

# Docentes: sus permisos reales dependen de la membresia aceptada en una
# institucion; el rol solo abre la puerta del router.
teacher_or_admin = RoleAuth(UserRole.ADMIN, UserRole.TEACHER)