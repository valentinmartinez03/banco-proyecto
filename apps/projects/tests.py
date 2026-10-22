"""Pruebas del circuito completo: el docente carga, la institucion aprueba.

Estan escritas contra la API y no contra los services: lo que hay que sostener
es lo que el sistema le responde a quien lo usa. Las unicas pruebas que llaman a
un service son las que comprueban una regla que la API no puede romper sola (la
transaccion que vuelve atras, el estado con el que nace un proyecto).
"""
import json
import shutil
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.academics.models import Career, Course, CourseStudent, CourseTerm, Student
from apps.accounts.models import UserRole
from apps.catalogs.models import Technology
from apps.institutions.models import (
    Institution,
    InstitutionEmailRule,
    InstitutionTeacher,
    MembershipOrigin,
    MembershipStatus,
)
from apps.projects import selectors, services
from apps.projects.models import AssetType, LinkType, Project, ProjectStatus
from apps.projects.schemas import ProjectFilters


TEST_MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="banco-proyectos-media-"))

# Un PNG de un pixel, para no depender de ningun archivo del repositorio.
PNG_DE_UN_PIXEL = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
    b"\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05"
    b"\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ProjectScenario(TestCase):
    """El escenario completo, sin pruebas propias.

    Armarlo cuesta varias tablas de varias apps, asi que se escribe una vez y
    las clases de abajo heredan de aca. Si en cambio una clase heredara de otra
    que ya tiene pruebas, esas pruebas volverian a correr enteras en cada hija,
    con un escenario distinto del que fueron escritas.

    Lo que monta es el circuito del MVP: una institucion con su cuenta, un
    docente aceptado, dos cursadas suyas con alumnos incorporados, y una segunda
    institucion con su propio docente para las pruebas de que nadie toca lo
    ajeno.
    """

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.user_model = get_user_model()

        self.institution = Institution.objects.create(name="IFTS 18", city="CABA")
        self.institution_user = self._create_institution_account(
            self.institution, "rectoria@ifts18.edu.ar"
        )
        self.teacher = self._create_teacher("diana@docentes.edu.ar", "Diana", "Docente")
        self.membership = self._accept_teacher(self.institution, self.teacher)

        self.career = Career.objects.create(
            institution=self.institution,
            name="Desarrollo de Software",
        )
        # Dos cursadas del mismo docente: el MVP pide que pueda tener mas de una.
        self.course = Course.objects.create(
            career=self.career,
            teacher=self.teacher,
            name="1C - Noche",
            year=2026,
            term=CourseTerm.FIRST,
        )
        self.other_course = Course.objects.create(
            career=self.career,
            teacher=self.teacher,
            name="2C - Manana",
            year=2026,
            term=CourseTerm.SECOND,
        )

        self.ana = self._enroll("Ana", "Gomez", self.course)
        self.bruno = self._enroll("Bruno", "Diaz", self.course)
        self.carla = self._enroll("Carla", "Ruiz", self.other_course)

        self.technology = Technology.objects.create(name="Django")
        self.other_technology = Technology.objects.create(name="React")

        # La otra institucion, con su propio docente y su propia cursada.
        self.other_institution = Institution.objects.create(name="IFTS 24", city="CABA")
        self.other_institution_user = self._create_institution_account(
            self.other_institution, "rectoria@ifts24.edu.ar"
        )
        self.other_teacher = self._create_teacher("hugo@docentes.edu.ar", "Hugo", "Perez")
        self.other_membership = self._accept_teacher(self.other_institution, self.other_teacher)

    # -- armado del escenario ------------------------------------------------

    def _create_institution_account(self, institution, email):
        user = self.user_model.objects.create_user(
            email=email,
            password="Rectoria12345!",
            first_name="Rectoria",
            last_name=institution.name,
            role=UserRole.INSTITUTION,
        )
        InstitutionEmailRule.objects.create(
            institution=institution,
            email=email,
            user=user,
        )
        return user

    def _create_teacher(self, email, first_name, last_name):
        return self.user_model.objects.create_user(
            email=email,
            password="Docente12345!",
            first_name=first_name,
            last_name=last_name,
            role=UserRole.TEACHER,
        )

    def _accept_teacher(self, institution, teacher):
        return InstitutionTeacher.objects.create(
            institution=institution,
            teacher=teacher,
            origin=MembershipOrigin.INVITATION,
            status=MembershipStatus.ACCEPTED,
        )

    def _enroll(self, first_name, last_name, course):
        """Carga un alumno en la institucion y lo inscribe en la cursada."""
        student = Student.objects.create(
            institution=course.career.institution,
            first_name=first_name,
            last_name=last_name,
            email=f"{first_name.lower()}@alumnos.edu.ar",
        )
        CourseStudent.objects.create(course=course, student=student)
        return student

    # -- atajos --------------------------------------------------------------

    def _login(self, email, password="Docente12345!"):
        response = self.client.post(
            "/api/auth/login",
            data=json.dumps({"email": email, "password": password}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access"]

    def _headers(self, email, password="Docente12345!"):
        return {"Authorization": f"Bearer {self._login(email, password)}"}

    def _payload(self, **overrides):
        payload = {
            "course_id": self.course.id,
            "team_name": "Equipo 3",
            "title": "Museo Virtual de Videojuegos",
            "summary": "Galeria de trabajos estudiantiles.",
            "description": "El detalle largo del trabajo.",
            "repository_url": "https://github.com/ifts/museo-virtual",
            "technology_ids": [self.technology.id],
            "student_ids": [self.ana.id],
        }
        payload.update(overrides)
        return payload

    def _post_project(self, email="diana@docentes.edu.ar", **overrides):
        return self.client.post(
            "/api/teacher/projects",
            data=json.dumps(self._payload(**overrides)),
            content_type="application/json",
            headers=self._headers(email),
        )

    def _create_project(self, status=ProjectStatus.APPROVED, students=None, **fields):
        """Atajo para las pruebas que necesitan un proyecto ya cargado."""
        data = {
            "course": self.course,
            "team_name": "Equipo 1",
            "title": "Proyecto de prueba",
            "summary": "Resumen",
            "status": status,
        }
        data.update(fields)
        project = Project.objects.create(**data)
        services.replace_students(project, students if students is not None else [self.ana])
        return project


class ProjectUploadTests(ProjectScenario):
    """Lo que el docente carga."""

    def test_teacher_uploads_a_project_and_it_starts_pending(self):
        response = self._post_project()
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["status"], ProjectStatus.PENDING)
        self.assertEqual(body["team_name"], "Equipo 3")
        self.assertEqual(body["teacher_name"], "Diana Docente")
        self.assertEqual(body["institution"]["name"], "IFTS 18")
        self.assertEqual([alumno["full_name"] for alumno in body["students"]], ["Ana Gomez"])
        # No lo reviso nadie todavia.
        self.assertIsNone(body["reviewed_at"])

    def test_a_teacher_loads_several_teams_in_the_same_course(self):
        """El pedido del MVP: varios proyectos por cursada, uno por equipo."""
        primero = self._post_project(team_name="Equipo 1", title="Museo Virtual")
        segundo = self._post_project(
            team_name="Equipo 2",
            title="Huerta Comunitaria",
            student_ids=[self.bruno.id],
        )
        self.assertEqual(primero.status_code, 200)
        self.assertEqual(segundo.status_code, 200)

        del_docente = self.client.get(
            "/api/teacher/projects",
            headers=self._headers("diana@docentes.edu.ar"),
        ).json()
        self.assertEqual(len(del_docente), 2)
        self.assertEqual(
            sorted(p["team_name"] for p in del_docente), ["Equipo 1", "Equipo 2"]
        )

    def test_a_teacher_loads_projects_of_more_than_one_course(self):
        self._post_project(course_id=self.course.id, student_ids=[self.ana.id])
        self._post_project(
            course_id=self.other_course.id,
            title="Ferias de Ciencias",
            student_ids=[self.carla.id],
        )

        del_docente = self.client.get(
            "/api/teacher/projects",
            headers=self._headers("diana@docentes.edu.ar"),
        ).json()
        self.assertEqual(
            sorted(p["course_name"] for p in del_docente), ["1C - Noche", "2C - Manana"]
        )

    def test_a_project_without_github_is_valid(self):
        """El banco no es solo de proyectos de programacion: una huerta, una
        muestra de disena o una campana sanitaria no tienen repositorio."""
        response = self._post_project(
            title="Huerta agroecologica",
            summary="Produccion de verdura en la terraza del instituto.",
            repository_url="",
            technology_ids=[],
            student_ids=[self.bruno.id],
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["repository_url"], "")
        self.assertEqual(body["technologies"], [])

    def test_the_repository_has_to_be_github(self):
        response = self._post_project(repository_url="https://gitlab.com/ifts/museo")
        self.assertEqual(response.status_code, 400)
        self.assertIn("repository_url", json.dumps(response.json()))

    def test_a_project_needs_at_least_one_student(self):
        response = self._post_project(student_ids=[])
        self.assertEqual(response.status_code, 400)
        self.assertIn("student_ids", json.dumps(response.json()))

    def test_the_students_have_to_be_enrolled_in_that_course(self):
        """Carla cursa la otra comision: no puede figurar en este trabajo."""
        response = self._post_project(student_ids=[self.ana.id, self.carla.id])
        self.assertEqual(response.status_code, 400)
        self.assertIn("student_ids", json.dumps(response.json()))

    def test_the_service_rolls_back_when_a_student_is_not_enrolled(self):
        """La comprobacion pasa antes de insertar, pero la transaccion tiene que
        sostenerlo igual: si fallara despues, no puede quedar el proyecto."""
        antes = Project.objects.count()
        with self.assertRaises(ValidationError):
            services.create_project(
                course_id=self.course.id,
                student_ids=[self.carla.id],
                technology_ids=[self.technology.id],
                title="A medio crear",
                summary="Resumen",
            )
        self.assertEqual(Project.objects.count(), antes)

    def test_a_student_with_a_project_cannot_be_removed_from_the_course(self):
        """La regla la sostiene academics; la prueba vive aca por el proyecto.

        Dar de baja una inscripcion con trabajo cargado dejaria un proyecto
        firmado por alguien que no curso. Lo que falta para probarlo es
        justamente un proyecto, y academics no conoce projects: ni su codigo ni
        sus pruebas, que en la guia se escriben varios pasos antes que esta app.
        """
        self._create_project(students=[self.ana])
        enrollment = CourseStudent.objects.get(course=self.course, student=self.ana)

        response = self.client.delete(
            f"/api/teacher/courses/{self.course.id}/students/{enrollment.id}",
            headers=self._headers("diana@docentes.edu.ar"),
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(CourseStudent.objects.filter(pk=enrollment.pk).exists())

    def test_another_teacher_cannot_upload_into_this_course(self):
        response = self._post_project(email="hugo@docentes.edu.ar")
        self.assertEqual(response.status_code, 403)

    def test_teacher_endpoints_need_a_token(self):
        self.assertEqual(self.client.get("/api/teacher/projects").status_code, 401)


class InstitutionUploadTests(ProjectScenario):
    """Lo que la institucion carga directo, sin pasar por el docente."""

    def _post_as_institution(self, email="rectoria@ifts18.edu.ar", **overrides):
        return self.client.post(
            "/api/institution/projects",
            data=json.dumps(self._payload(**overrides)),
            content_type="application/json",
            headers=self._headers(email, "Rectoria12345!"),
        )

    def test_the_institution_uploads_a_project_and_it_is_born_approved(self):
        response = self._post_as_institution()
        self.assertEqual(response.status_code, 200)

        body = response.json()
        self.assertEqual(body["status"], ProjectStatus.APPROVED)
        # La revision queda firmada por quien lo cargo: la institucion no se
        # aprueba a si misma, pero tampoco deja el proyecto como "sin revisar".
        self.assertIsNotNone(body["reviewed_at"])
        self.assertEqual(Project.objects.get(pk=body["id"]).reviewed_by, self.institution_user)
        # Y ya esta en el catalogo, sin que nadie tenga que aprobarlo.
        catalogo = self.client.get("/api/projects").json()
        self.assertEqual([p["id"] for p in catalogo], [body["id"]])

    def test_another_institution_cannot_upload_into_this_course(self):
        response = self._post_as_institution(email="rectoria@ifts24.edu.ar")
        self.assertEqual(response.status_code, 403)


class ProjectFilesAndLinksTests(ProjectScenario):
    """Las dos mitades de "todo lo relacionado": lo que se sube y lo que se linkea."""

    def setUp(self):
        super().setUp()
        self.project = self._create_project(status=ProjectStatus.PENDING)
        self.headers = self._headers("diana@docentes.edu.ar")

    def test_teacher_uploads_a_cover_image(self):
        response = self.client.post(
            f"/api/teacher/projects/{self.project.id}/assets",
            data={
                "asset_type": AssetType.IMAGE,
                "title": "Pantalla principal",
                "is_cover": "true",
                "file": SimpleUploadedFile("captura.png", PNG_DE_UN_PIXEL, "image/png"),
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["is_cover"])
        self.assertTrue(body["file_url"].endswith(".png"))

    def test_only_one_image_is_the_cover(self):
        for nombre in ("primera.png", "segunda.png"):
            self.client.post(
                f"/api/teacher/projects/{self.project.id}/assets",
                data={
                    "asset_type": AssetType.IMAGE,
                    "is_cover": "true",
                    "file": SimpleUploadedFile(nombre, PNG_DE_UN_PIXEL, "image/png"),
                },
                headers=self.headers,
            )
        self.assertEqual(self.project.assets.filter(is_cover=True).count(), 1)

    def test_a_video_does_not_enter_as_an_image(self):
        response = self.client.post(
            f"/api/teacher/projects/{self.project.id}/assets",
            data={
                "asset_type": AssetType.IMAGE,
                "file": SimpleUploadedFile("defensa.mp4", b"0000", "video/mp4"),
            },
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 400)

    def test_teacher_adds_links_and_they_do_not_repeat(self):
        cuerpo = {
            "link_type": LinkType.DEMO,
            "title": "Demo publicada",
            "url": "https://museo.vercel.app",
        }
        primera = self.client.post(
            f"/api/teacher/projects/{self.project.id}/links",
            data=json.dumps(cuerpo),
            content_type="application/json",
            headers=self.headers,
        )
        self.assertEqual(primera.status_code, 200)

        repetida = self.client.post(
            f"/api/teacher/projects/{self.project.id}/links",
            data=json.dumps(cuerpo),
            content_type="application/json",
            headers=self.headers,
        )
        self.assertEqual(repetida.status_code, 400)

    def test_another_teacher_cannot_touch_the_files(self):
        response = self.client.post(
            f"/api/teacher/projects/{self.project.id}/assets",
            data={
                "asset_type": AssetType.IMAGE,
                "file": SimpleUploadedFile("captura.png", PNG_DE_UN_PIXEL, "image/png"),
            },
            headers=self._headers("hugo@docentes.edu.ar"),
        )
        self.assertEqual(response.status_code, 403)


class ProjectReviewTests(ProjectScenario):
    """La revision de la institucion."""

    def setUp(self):
        super().setUp()
        self.project = self._create_project(status=ProjectStatus.PENDING)
        self.institution_headers = {
            "Authorization": f"Bearer {self._login('rectoria@ifts18.edu.ar', 'Rectoria12345!')}"
        }

    def _review(self, accion, headers=None, **cuerpo):
        return self.client.post(
            f"/api/institution/projects/{self.project.id}/{accion}",
            data=json.dumps(cuerpo),
            content_type="application/json",
            headers=headers or self.institution_headers,
        )

    def test_the_pending_tray_shows_what_is_waiting(self):
        response = self.client.get(
            "/api/institution/projects?status=PENDING",
            headers=self.institution_headers,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p["id"] for p in response.json()], [self.project.id])

    def test_approving_publishes_it_in_the_public_catalog(self):
        self.assertEqual(self.client.get("/api/projects").json(), [])

        response = self._review("approve")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], ProjectStatus.APPROVED)

        catalogo = self.client.get("/api/projects").json()
        self.assertEqual([p["id"] for p in catalogo], [self.project.id])

    def test_returning_a_project_needs_written_feedback(self):
        sin_texto = self._review("request-changes", notes="   ")
        self.assertEqual(sin_texto.status_code, 400)

        con_texto = self._review("request-changes", notes="Falta la portada.")
        self.assertEqual(con_texto.status_code, 200)
        self.assertEqual(con_texto.json()["status"], ProjectStatus.CHANGES)
        self.assertEqual(con_texto.json()["review_notes"], "Falta la portada.")

    def test_rejecting_also_needs_feedback(self):
        self.assertEqual(self._review("reject").status_code, 400)
        self.assertEqual(
            self._review("reject", notes="No corresponde al banco.").status_code, 200
        )

    def test_the_feedback_survives_while_the_teacher_corrects(self):
        self._review("request-changes", notes="Falta la portada.")

        self.client.patch(
            f"/api/teacher/projects/{self.project.id}",
            data=json.dumps({"summary": "Resumen corregido"}),
            content_type="application/json",
            headers=self._headers("diana@docentes.edu.ar"),
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, ProjectStatus.PENDING)
        self.assertEqual(self.project.review_notes, "Falta la portada.")

    def test_the_teacher_reads_the_feedback_in_his_own_file(self):
        """La devolucion se lee por la ficha del docente, no por el catalogo.

        El catalogo publico sirve solo lo aprobado, y la lista del docente
        contesta la version corta, que no la trae: por eso existe la ficha
        propia, que devuelve el proyecto entero en el estado que tenga.
        """
        self._review("request-changes", notes="Falta la portada.")

        publica = self.client.get(f"/api/projects/{self.project.slug}")
        self.assertEqual(publica.status_code, 404)

        propia = self.client.get(
            f"/api/teacher/projects/{self.project.id}",
            headers=self._headers("diana@docentes.edu.ar"),
        )
        self.assertEqual(propia.status_code, 200)
        self.assertEqual(propia.json()["review_notes"], "Falta la portada.")

        ajena = self.client.get(
            f"/api/teacher/projects/{self.project.id}",
            headers=self._headers("hugo@docentes.edu.ar"),
        )
        self.assertEqual(ajena.status_code, 403)

    def test_editing_returns_an_approved_project_to_the_queue(self):
        self._review("approve")
        self.client.patch(
            f"/api/teacher/projects/{self.project.id}",
            data=json.dumps({"title": "Museo Virtual, segunda version"}),
            content_type="application/json",
            headers=self._headers("diana@docentes.edu.ar"),
        )
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, ProjectStatus.PENDING)
        self.assertIsNone(self.project.reviewed_by)
        self.assertIsNone(self.project.reviewed_at)

    def test_another_institution_cannot_review_it(self):
        otras_credenciales = {
            "Authorization": f"Bearer {self._login('rectoria@ifts24.edu.ar', 'Rectoria12345!')}"
        }
        response = self._review("approve", headers=otras_credenciales)
        self.assertEqual(response.status_code, 403)


class PublishingPrivilegeTests(ProjectScenario):
    """El privilegio de publicar sin revision.

    Es la segunda mitad del pedido: la institucion aprueba, o le da al docente
    el permiso de subir sin esperar aprobacion.
    """

    def setUp(self):
        super().setUp()
        self.institution_headers = {
            "Authorization": f"Bearer {self._login('rectoria@ifts18.edu.ar', 'Rectoria12345!')}"
        }

    def _grant(self, membership=None, allowed=True, headers=None):
        membership = membership or self.membership
        return self.client.put(
            f"/api/institution/teachers/{membership.id}/publishing",
            data=json.dumps({"allowed": allowed}),
            content_type="application/json",
            headers=headers or self.institution_headers,
        )

    def test_a_project_of_a_trusted_teacher_is_born_approved(self):
        self.membership.set_publishing_privilege(True)

        body = self._post_project().json()
        self.assertEqual(body["status"], ProjectStatus.APPROVED)
        # Aprobado pero sin revisar: es lo que distingue despues la confianza de
        # una decision que la institucion tomo mirando el trabajo.
        self.assertIsNone(body["reviewed_at"])
        self.assertEqual(
            [p["id"] for p in self.client.get("/api/projects").json()], [body["id"]]
        )

    def test_editing_does_not_send_it_back_to_the_queue(self):
        self.membership.set_publishing_privilege(True)
        project_id = self._post_project().json()["id"]

        self.client.patch(
            f"/api/teacher/projects/{project_id}",
            data=json.dumps({"summary": "Resumen corregido"}),
            content_type="application/json",
            headers=self._headers("diana@docentes.edu.ar"),
        )
        self.assertEqual(
            Project.objects.get(pk=project_id).status, ProjectStatus.APPROVED
        )

    def test_revoking_it_sends_the_next_edit_back_to_the_queue(self):
        self.membership.set_publishing_privilege(True)
        project_id = self._post_project().json()["id"]

        self._grant(allowed=False)

        self.client.patch(
            f"/api/teacher/projects/{project_id}",
            data=json.dumps({"summary": "Otra correccion"}),
            content_type="application/json",
            headers=self._headers("diana@docentes.edu.ar"),
        )
        self.assertEqual(
            Project.objects.get(pk=project_id).status, ProjectStatus.PENDING
        )

    def test_revoking_it_does_not_unpublish_what_was_already_published(self):
        self.membership.set_publishing_privilege(True)
        project_id = self._post_project().json()["id"]

        self._grant(allowed=False)
        self.assertEqual(
            Project.objects.get(pk=project_id).status, ProjectStatus.APPROVED
        )

    def test_the_privilege_is_per_institution(self):
        """Diana publica directo en el IFTS 18 y espera revision en el IFTS 24."""
        self.membership.set_publishing_privilege(True)

        otra_carrera = Career.objects.create(
            institution=self.other_institution, name="Analisis de Sistemas"
        )
        otra_cursada = Course.objects.create(
            career=otra_carrera,
            teacher=self.teacher,
            name="1C - Noche",
            year=2026,
            term=CourseTerm.FIRST,
        )
        self._accept_teacher(self.other_institution, self.teacher)
        alumna = Student.objects.create(
            institution=self.other_institution, first_name="Delia", last_name="Vera"
        )
        CourseStudent.objects.create(course=otra_cursada, student=alumna)

        aca = self._post_project().json()
        alla = self._post_project(
            course_id=otra_cursada.id,
            title="Otro instituto",
            student_ids=[alumna.id],
            technology_ids=[],
        ).json()

        self.assertEqual(aca["status"], ProjectStatus.APPROVED)
        self.assertEqual(alla["status"], ProjectStatus.PENDING)

    def test_the_institution_grants_it_through_the_api(self):
        response = self._grant()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["publishes_without_review"])

        self.membership.refresh_from_db()
        self.assertTrue(self.membership.publishes_without_review)

    def test_another_institution_cannot_grant_it(self):
        otras_credenciales = {
            "Authorization": f"Bearer {self._login('rectoria@ifts24.edu.ar', 'Rectoria12345!')}"
        }
        response = self._grant(headers=otras_credenciales)
        self.assertEqual(response.status_code, 403)
        self.membership.refresh_from_db()
        self.assertFalse(self.membership.publishes_without_review)

    def test_the_teacher_cannot_grant_it_to_himself(self):
        """El router pide rol de institucion, asi que el docente ni entra: es un
        403 (esta identificado y no le corresponde) y no un 401."""
        response = self._grant(headers=self._headers("diana@docentes.edu.ar"))
        self.assertEqual(response.status_code, 403)

    def test_it_needs_an_accepted_membership(self):
        pendiente = InstitutionTeacher.objects.create(
            institution=self.institution,
            teacher=self._create_teacher("nueva@docentes.edu.ar", "Nora", "Nueva"),
            origin=MembershipOrigin.REQUEST,
            status=MembershipStatus.PENDING,
        )
        response = self._grant(membership=pendiente)
        self.assertEqual(response.status_code, 400)


class PublicCatalogTests(ProjectScenario):
    """Lo que ve cualquiera, sin iniciar sesion."""

    def setUp(self):
        super().setUp()
        self.museo = self._create_project(
            title="Museo Virtual",
            summary="Galeria de trabajos",
            team_name="Equipo 1",
            students=[self.ana, self.bruno],
        )
        services.replace_technologies(self.museo, [self.technology.id])
        self.huerta = self._create_project(
            course=self.other_course,
            title="Huerta agroecologica",
            summary="Verdura en la terraza",
            team_name="Equipo 2",
            students=[self.carla],
        )
        self.pendiente = self._create_project(
            title="Todavia sin aprobar",
            status=ProjectStatus.PENDING,
        )

    def test_the_catalog_needs_no_token_and_hides_what_is_not_approved(self):
        response = self.client.get("/api/projects")
        self.assertEqual(response.status_code, 200)
        titulos = sorted(p["title"] for p in response.json())
        self.assertEqual(titulos, ["Huerta agroecologica", "Museo Virtual"])

    def test_the_file_shows_the_students_that_the_teacher_loaded(self):
        response = self.client.get(f"/api/projects/{self.museo.slug}")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(
            sorted(alumno["full_name"] for alumno in body["students"]),
            ["Ana Gomez", "Bruno Diaz"],
        )
        self.assertEqual(body["teacher_name"], "Diana Docente")
        self.assertEqual(body["course"]["name"], "1C - Noche")

    def test_a_project_that_is_not_approved_answers_404_and_not_403(self):
        """Un 403 contaria que existe: lo que no esta publicado no existe para
        el que mira desde afuera."""
        response = self.client.get(f"/api/projects/{self.pendiente.slug}")
        self.assertEqual(response.status_code, 404)

    def test_the_filters_combine(self):
        respuesta = self.client.get(
            f"/api/projects?course_id={self.course.id}&technology_id={self.technology.id}"
        )
        self.assertEqual([p["title"] for p in respuesta.json()], ["Museo Virtual"])

        por_alumno = self.client.get("/api/projects?student=carla")
        self.assertEqual([p["title"] for p in por_alumno.json()], ["Huerta agroecologica"])

        por_equipo = self.client.get("/api/projects?team=Equipo 2")
        self.assertEqual([p["title"] for p in por_equipo.json()], ["Huerta agroecologica"])

    def test_a_team_project_is_not_duplicated_when_filtering_by_student(self):
        """El filtro por alumno cruza una relacion de a muchos: sin distinct(),
        el Museo aparecia una vez por cada integrante que coincidiera."""
        respuesta = self.client.get("/api/projects?student=o")
        ids = [p["id"] for p in respuesta.json()]
        self.assertEqual(len(ids), len(set(ids)))

    def test_the_selector_applies_the_same_filters_as_the_api(self):
        filtros = ProjectFilters(course_id=self.course.id)
        self.assertEqual(
            [p.title for p in selectors.public_catalog(filtros)], ["Museo Virtual"]
        )
