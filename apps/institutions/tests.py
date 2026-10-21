import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import UserRole
from apps.institutions.models import (
    Institution,
    InstitutionEmailRule,
    InstitutionTeacher,
    MembershipOrigin,
    MembershipStatus,
)


class InstitutionsApiTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.institution = Institution.objects.create(name="IFTS 18", city="CABA")
        # Email habilitado desde el admin, todavia sin activar.
        self.rule = InstitutionEmailRule.objects.create(
            institution=self.institution,
            email="rectoria@ifts18.edu.ar",
        )
        self.teacher = self.user_model.objects.create_user(
            email="diana@docentes.edu.ar",
            password="Docente12345!",
            first_name="Diana",
            last_name="Docente",
            role=UserRole.TEACHER,
        )

    def _login(self, email, password):
        response = self.client.post(
            "/api/auth/login",
            data=json.dumps({"email": email, "password": password}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["access"]

    def _activate_institution(self):
        response = self.client.post(
            "/api/institutions/activate",
            data=json.dumps(
                {
                    "email": "rectoria@ifts18.edu.ar",
                    "password": "Rectoria12345!",
                    "first_name": "Rectoria",
                    "last_name": "IFTS",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        return self._login("rectoria@ifts18.edu.ar", "Rectoria12345!")

    def test_public_list_needs_no_token(self):
        response = self.client.get("/api/institutions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["name"], "IFTS 18")

    def test_enabled_email_can_activate_account(self):
        """El circuito de entrada: el email habilitado crea su contrasena y la
        cuenta queda a cargo de la institucion."""
        access = self._activate_institution()

        response = self.client.get(
            "/api/institution/teachers",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(response.status_code, 200)

        self.rule.refresh_from_db()
        self.assertTrue(self.rule.is_activated)

    def test_not_enabled_email_cannot_activate(self):
        response = self.client.post(
            "/api/institutions/activate",
            data=json.dumps(
                {
                    "email": "cualquiera@gmail.com",
                    "password": "Clave12345!",
                    "first_name": "Nadie",
                    "last_name": "Nada",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_email_cannot_activate_twice(self):
        self._activate_institution()

        response = self.client.post(
            "/api/institutions/activate",
            data=json.dumps(
                {
                    "email": "rectoria@ifts18.edu.ar",
                    "password": "OtraClave12345!",
                    "first_name": "Otra",
                    "last_name": "Persona",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_institution_invites_and_teacher_accepts(self):
        institution_access = self._activate_institution()

        response = self.client.post(
            "/api/institution/teachers/invite",
            data=json.dumps({"teacher_email": "diana@docentes.edu.ar"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {institution_access}",
        )
        self.assertEqual(response.status_code, 200)
        membership_id = response.json()["id"]
        self.assertEqual(response.json()["status"], MembershipStatus.PENDING)

        # La invitacion la responde el docente, no la institucion.
        teacher_access = self._login("diana@docentes.edu.ar", "Docente12345!")
        response = self.client.post(
            f"/api/teacher/memberships/{membership_id}/accept",
            HTTP_AUTHORIZATION=f"Bearer {teacher_access}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], MembershipStatus.ACCEPTED)

    def test_teacher_requests_and_institution_accepts(self):
        institution_access = self._activate_institution()
        teacher_access = self._login("diana@docentes.edu.ar", "Docente12345!")

        response = self.client.post(
            "/api/teacher/memberships",
            data=json.dumps({"institution_id": self.institution.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {teacher_access}",
        )
        self.assertEqual(response.status_code, 200)
        membership_id = response.json()["id"]

        # La solicitud no la puede responder el mismo docente.
        response = self.client.post(
            f"/api/teacher/memberships/{membership_id}/accept",
            HTTP_AUTHORIZATION=f"Bearer {teacher_access}",
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            f"/api/institution/teachers/{membership_id}/accept",
            HTTP_AUTHORIZATION=f"Bearer {institution_access}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], MembershipStatus.ACCEPTED)

    def test_membership_is_unique_per_institution_and_teacher(self):
        institution_access = self._activate_institution()
        InstitutionTeacher.objects.create(
            institution=self.institution,
            teacher=self.teacher,
            origin=MembershipOrigin.REQUEST,
        )

        response = self.client.post(
            "/api/institution/teachers/invite",
            data=json.dumps({"teacher_email": "diana@docentes.edu.ar"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {institution_access}",
        )
        self.assertEqual(response.status_code, 400)

    def test_invite_requires_a_registered_teacher(self):
        institution_access = self._activate_institution()

        response = self.client.post(
            "/api/institution/teachers/invite",
            data=json.dumps({"teacher_email": "nadie@docentes.edu.ar"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {institution_access}",
        )
        self.assertEqual(response.status_code, 400)

    def test_membership_cannot_be_answered_twice(self):
        institution_access = self._activate_institution()
        membership = InstitutionTeacher.objects.create(
            institution=self.institution,
            teacher=self.teacher,
            origin=MembershipOrigin.REQUEST,
            status=MembershipStatus.ACCEPTED,
        )

        response = self.client.post(
            f"/api/institution/teachers/{membership.id}/reject",
            HTTP_AUTHORIZATION=f"Bearer {institution_access}",
        )
        self.assertEqual(response.status_code, 400)

    def test_institution_cannot_answer_a_request_of_another_institution(self):
        """El rol del router abre la puerta; la pertenencia se pregunta por objeto."""
        institution_access = self._activate_institution()
        other_institution = Institution.objects.create(name="IFTS 24", city="CABA")
        membership = InstitutionTeacher.objects.create(
            institution=other_institution,
            teacher=self.teacher,
            origin=MembershipOrigin.REQUEST,
        )

        response = self.client.post(
            f"/api/institution/teachers/{membership.id}/accept",
            HTTP_AUTHORIZATION=f"Bearer {institution_access}",
        )
        self.assertEqual(response.status_code, 403)
