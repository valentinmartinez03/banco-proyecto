"""Pruebas del circuito del docente: su cursada y los alumnos que carga.

El escenario es caro de armar (institucion, cuenta institucional, docente,
membresia aceptada y carrera), asi que se arma una vez en una clase base sin
pruebas y las demas heredan de ella.
"""
import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.academics import selectors
from apps.academics.models import Career, Course, CourseStudent, CourseTerm, Student
from apps.accounts.models import UserRole
from apps.institutions.models import (
    Institution,
    InstitutionEmailRule,
    InstitutionTeacher,
    MembershipOrigin,
    MembershipStatus,
)

class AcademicsTestCase(TestCase):
    """Escenario compartido: una institucion, su cuenta, un docente y una carrera."""

    def setUp(self):
        self.user_model = get_user_model()
        # Los datos de las otras apps se crean aca: esta app depende de ellas,
        # asi que sus tests tambien.
        self.institution = Institution.objects.create(name="IFTS 18", city="CABA")
        self.institution_user = self.user_model.objects.create_user(
            email="rectoria@ifts18.edu.ar",
            password="Rectoria12345!",
            first_name="Rectoria",
            last_name="IFTS",
            role=UserRole.INSTITUTION,
        )
        InstitutionEmailRule.objects.create(
            institution=self.institution,
            email="rectoria@ifts18.edu.ar",
            user=self.institution_user,
        )
        self.teacher = self.user_model.objects.create_user(
            email="diana@docentes.edu.ar",
            password="Docente12345!",
            first_name="Diana",
            last_name="Docente",
            role=UserRole.TEACHER,
        )
        self.membership = InstitutionTeacher.objects.create(
            institution=self.institution,
            teacher=self.teacher,
            origin=MembershipOrigin.INVITATION,
            status=MembershipStatus.ACCEPTED,
        )
        self.career = Career.objects.create(
            institution=self.institution,
            name="Desarrollo de Software",
        )

    def _login(self, email, password):
        response = self.client.post(
            "/api/auth/login",
            data=json.dumps({"email": email, "password": password}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access"]

    def _post(self, url, payload, access):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )

    def _create_course(self, name="1C - Noche", teacher=None, year=2026):
        return Course.objects.create(
            career=self.career,
            teacher=teacher or self.teacher,
            name=name,
            year=year,
            term=CourseTerm.FIRST,
        )


class CareerApiTests(AcademicsTestCase):
    def test_public_careers_need_no_token(self):
        response = self.client.get(f"/api/careers?institution_id={self.institution.id}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["name"], "Desarrollo de Software")

    def test_institution_creates_career(self):
        access = self._login("rectoria@ifts18.edu.ar", "Rectoria12345!")

        response = self._post("/api/institution/careers", {"name": "Ciencia de Datos"}, access)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Career.objects.filter(institution=self.institution, name="Ciencia de Datos").exists()
        )

    def test_career_name_cannot_repeat_in_the_same_institution(self):
        """La comparacion no distingue mayusculas: es la misma carrera."""
        access = self._login("rectoria@ifts18.edu.ar", "Rectoria12345!")

        response = self._post(
            "/api/institution/careers", {"name": "desarrollo de software"}, access
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Career.objects.filter(institution=self.institution).count(), 1)


class CourseApiTests(AcademicsTestCase):
    def test_member_teacher_creates_course(self):
        access = self._login("diana@docentes.edu.ar", "Docente12345!")

        response = self._post(
            "/api/teacher/courses",
            {
                "career_id": self.career.id,
                "name": "1C - Noche",
                "year": 2026,
                "term": CourseTerm.FIRST.value,
            },
            access,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["career"]["name"], "Desarrollo de Software")
        self.assertEqual(response.json()["term_label"], "Primer cuatrimestre")

    def test_non_member_teacher_cannot_create_course(self):
        """Ser TEACHER no alcanza: la membresia aceptada es el permiso real."""
        self.user_model.objects.create_user(
            email="externo@docentes.edu.ar",
            password="Docente12345!",
            first_name="Elias",
            last_name="Externo",
            role=UserRole.TEACHER,
        )
        access = self._login("externo@docentes.edu.ar", "Docente12345!")

        response = self._post(
            "/api/teacher/courses",
            {
                "career_id": self.career.id,
                "name": "1C - Noche",
                "year": 2026,
                "term": CourseTerm.FIRST.value,
            },
            access,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Course.objects.exists())

    def test_a_pending_membership_is_not_enough(self):
        self.membership.status = MembershipStatus.PENDING
        self.membership.save(update_fields=["status"])
        access = self._login("diana@docentes.edu.ar", "Docente12345!")

        response = self._post(
            "/api/teacher/courses",
            {
                "career_id": self.career.id,
                "name": "1C - Noche",
                "year": 2026,
                "term": CourseTerm.FIRST.value,
            },
            access,
        )

        self.assertEqual(response.status_code, 400)

    def test_invalid_term_is_rejected(self):
        """El periodo llega como texto: si no es una opcion, no se guarda nada."""
        access = self._login("diana@docentes.edu.ar", "Docente12345!")

        response = self._post(
            "/api/teacher/courses",
            {
                "career_id": self.career.id,
                "name": "1C - Noche",
                "year": 2026,
                "term": "VERANO",
            },
            access,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Course.objects.exists())

    def test_course_answers_its_institution_through_the_career(self):
        """La cursada no guarda la institucion y sin embargo la sabe."""
        course = self._create_course()

        self.assertEqual(course.institution, self.institution)


class EnrollmentApiTests(AcademicsTestCase):
    def setUp(self):
        super().setUp()
        self.course = self._create_course()
        self.access = self._login("diana@docentes.edu.ar", "Docente12345!")

    def _enroll(self, course, first_name="Ana", last_name="Gomez", email=""):
        return self._post(
            f"/api/teacher/courses/{course.id}/students",
            {"first_name": first_name, "last_name": last_name, "email": email},
            self.access,
        )

    def test_teacher_loads_a_student_and_no_account_is_created(self):
        """El alumno es un dato del docente: ya no nace una cuenta con el."""
        response = self._enroll(self.course, email="ana@alumnos.edu.ar")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["student"]["full_name"], "Ana Gomez")
        student = Student.objects.get(email="ana@alumnos.edu.ar")
        self.assertEqual(student.institution, self.institution)
        self.assertFalse(self.user_model.objects.filter(email="ana@alumnos.edu.ar").exists())

    def test_the_same_email_reuses_the_student_of_the_institution(self):
        """Ana cursa dos materias: es una sola alumna con dos inscripciones."""
        other_course = self._create_course(name="2C - Manana")

        self._enroll(self.course, email="ana@alumnos.edu.ar")
        self._enroll(other_course, email="ANA@alumnos.edu.ar")

        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(CourseStudent.objects.count(), 2)

    def test_students_without_email_are_not_mixed_up(self):
        """Sin email no hay con que compararlos: son dos alumnos distintos."""
        self._enroll(self.course, first_name="Ana", last_name="Gomez")
        self._enroll(self.course, first_name="Luis", last_name="Perez")

        self.assertEqual(Student.objects.count(), 2)

    def test_student_cannot_be_enrolled_twice_in_the_same_course(self):
        self._enroll(self.course, email="ana@alumnos.edu.ar")

        response = self._enroll(self.course, email="ana@alumnos.edu.ar")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(CourseStudent.objects.filter(course=self.course).count(), 1)

    def test_teacher_cannot_touch_another_teachers_course(self):
        other_teacher = self.user_model.objects.create_user(
            email="otro@docentes.edu.ar",
            password="Docente12345!",
            first_name="Omar",
            last_name="Otro",
            role=UserRole.TEACHER,
        )
        InstitutionTeacher.objects.create(
            institution=self.institution,
            teacher=other_teacher,
            origin=MembershipOrigin.REQUEST,
            status=MembershipStatus.ACCEPTED,
        )
        self.access = self._login("otro@docentes.edu.ar", "Docente12345!")

        response = self._enroll(self.course, email="ana@alumnos.edu.ar")

        self.assertEqual(response.status_code, 403)

    def test_removing_an_enrollment_keeps_the_student(self):
        """Se da de baja la inscripcion, no al alumno: sigue en la institucion."""
        self._enroll(self.course, email="ana@alumnos.edu.ar")
        enrollment = CourseStudent.objects.get(course=self.course)

        response = self.client.delete(
            f"/api/teacher/courses/{self.course.id}/students/{enrollment.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(CourseStudent.objects.filter(pk=enrollment.pk).exists())
        self.assertTrue(Student.objects.filter(email="ana@alumnos.edu.ar").exists())

    def test_an_enrollment_of_another_course_is_not_found(self):
        """El id se busca dentro de la cursada, asi no se borra lo ajeno."""
        other_course = self._create_course(name="2C - Manana")
        self._enroll(other_course, email="ana@alumnos.edu.ar")
        enrollment = CourseStudent.objects.get(course=other_course)

        response = self.client.delete(
            f"/api/teacher/courses/{self.course.id}/students/{enrollment.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.access}",
        )

        self.assertEqual(response.status_code, 404)

    def test_only_students_enrolled_in_the_course_come_back(self):
        """Es la pregunta que hace projects para validar los participantes."""
        self._enroll(self.course, email="ana@alumnos.edu.ar")
        outsider = Student.objects.create(
            institution=self.institution,
            first_name="Luis",
            last_name="Perez",
            email="luis@alumnos.edu.ar",
        )
        enrolled = Student.objects.get(email="ana@alumnos.edu.ar")

        found = selectors.students_enrolled_in_course(
            self.course, [enrolled.id, outsider.id]
        )

        self.assertEqual(list(found), [enrolled])
