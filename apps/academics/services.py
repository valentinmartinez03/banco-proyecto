"""Operaciones que modifican carreras, cursadas y alumnos.

El circuito se lee en los nombres: la institucion crea carreras, el docente que
forma parte de ella abre cursadas, y en esas cursadas carga a sus alumnos.

Las reglas viven aca y no en la API: son verdades del negocio y valen igual si
manana el alta se hace desde el admin, desde un comando o desde un test.
"""
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.academics import selectors
from apps.academics.models import Career, Course, CourseStudent, CourseTerm, Student
from apps.accounts.models import UserRole
from apps.institutions import selectors as institutions_selectors


def create_career(institution, *, name):
    """Alta de una carrera.

    El nombre se compara sin distinguir mayusculas: "Desarrollo de Software" y
    "desarrollo de software" son la misma carrera y la restriccion de la base,
    que compara tal cual, no lo notaria.
    """
    name = name.strip()
    if Career.objects.of_institution(institution).filter(name__iexact=name).exists():
        raise ValidationError({"name": "La institucion ya tiene una carrera con ese nombre."})
    return Career.objects.create(institution=institution, name=name)


def create_course(teacher, *, career_id, name, year, term):
    """Alta de una cursada, hecha por el docente que la va a dictar.

    Aca aparece la regla de permisos del docente: no alcanza con tener el rol
    TEACHER (eso solo abre la puerta del router), hay que tener la membresia
    aceptada en la institucion duena de la carrera. El administrador queda
    afuera de la regla porque no representa a ninguna institucion: destraba.

    El periodo llega como texto desde la API, asi que se valida contra las
    opciones antes de guardar: el choices del modelo no valida solo en un
    create(), solo arma el formulario y el admin.
    """
    career = selectors.career(career_id)
    membership = institutions_selectors.accepted_membership(teacher, career.institution)
    if membership is None and teacher.role != UserRole.ADMIN:
        raise ValidationError(
            {"career_id": "El docente no forma parte de la institucion de esa carrera."}
        )

    if term not in CourseTerm.values:
        raise ValidationError(
            {"term": f"Periodo invalido. Opciones: {', '.join(CourseTerm.values)}."}
        )

    return Course.objects.create(
        career=career,
        teacher=teacher,
        name=name.strip(),
        year=year,
        term=term,
    )


@transaction.atomic
def enroll_student(course, *, first_name, last_name, email=""):
    """Carga un alumno en una cursada, reusando el que ya existe en la institucion.

    El email es la unica forma de reconocer a alguien que ya fue cargado: si
    coincide con el de un alumno de esa institucion, se lo inscribe a ese en vez
    de duplicarlo, y asi los proyectos de las dos cursadas quedan atados a la
    misma persona. Sin email no hay con que comparar, y cada carga crea un
    alumno nuevo.

    Ya no se crean cuentas de usuario: el alumno no entra a la plataforma, es un
    dato del docente.

    La funcion es atomica porque hace dos cosas seguidas: puede crear el alumno
    y despues rechazar la inscripcion por repetida. Sin la transaccion quedaria
    un alumno dado de alta por una inscripcion que nunca ocurrio.
    """
    first_name = first_name.strip()
    last_name = last_name.strip()
    email = email.strip().lower()

    if not first_name or not last_name:
        raise ValidationError({"last_name": "El alumno necesita nombre y apellido."})

    institution = course.institution
    student = None
    if email:
        student = Student.objects.of_institution(institution).with_email(email).first()

    if student is None:
        student = Student.objects.create(
            institution=institution,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )

    if CourseStudent.objects.of_course(course).filter(student=student).exists():
        raise ValidationError({"student": "El alumno ya esta inscripto en esta cursada."})

    return CourseStudent.objects.create(course=course, student=student)


def remove_enrollment(enrollment):
    """Saca a un alumno de una cursada.

    Se borra la inscripcion, no el alumno: sigue existiendo en la institucion y
    en las demas cursadas donde este.

    No se puede sacar a alguien que figura como participante de un proyecto de
    esa misma cursada: quedaria un proyecto firmado por alguien que, segun el
    sistema, nunca la curso. Primero se lo saca del proyecto.

    La pregunta por los proyectos se hace por la relacion inversa que declara la
    app de proyectos (related_name="project_participations") y no importando su
    modelo. Es a proposito: projects depende de academics, y si academics
    importara projects las dos apps quedarian atadas en circulo.

    Por eso mismo se pregunta con getattr: la relacion inversa aparece recien
    cuando esa app existe, y esta app tiene que funcionar igual sin ella. Es
    literalmente lo que pasa mientras se construye el sistema, donde academics
    se escribe antes que projects: sin alumnos en ningun proyecto, no hay nada
    que impida la baja.
    """
    participations = getattr(enrollment.student, "project_participations", None)
    if participations is not None and participations.filter(project__course=enrollment.course).exists():
        raise ValidationError(
            {
                "enrollment_id": (
                    "El alumno figura en un proyecto de esta cursada: primero hay que "
                    "sacarlo del proyecto."
                )
            }
        )
    enrollment.delete()
