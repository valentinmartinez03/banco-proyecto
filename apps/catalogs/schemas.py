from ninja import Schema


class TechnologyOut(Schema):
    """Lo que ve el que consume la API: id para filtrar, nombre para mostrar.

    created_at no se expone porque a nadie le sirve saber cuando se cargo una
    tecnologia; el esquema dice que sale, no el modelo.
    """

    id: int
    name: str
