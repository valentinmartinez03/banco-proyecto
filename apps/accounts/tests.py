import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import UserRole


class AccountsApiTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()
        self.admin = self.user_model.objects.create_superuser(
            email="admin@plataforma.edu.ar",
            password="Admin12345!",
            first_name="Ada",
            last_name="Admin",
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

    def test_login_returns_token_pair(self):
        response = self.client.post(
            "/api/auth/login",
            data=json.dumps({"email": "diana@docentes.edu.ar", "password": "Docente12345!"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("access", body)
        self.assertIn("refresh", body)

    def test_login_rejects_bad_credentials(self):
        response = self.client.post(
            "/api/auth/login",
            data=json.dumps({"email": "diana@docentes.edu.ar", "password": "otra"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    def test_refresh_returns_a_new_token_pair(self):
        response = self.client.post(
            "/api/auth/login",
            data=json.dumps({"email": "diana@docentes.edu.ar", "password": "Docente12345!"}),
            content_type="application/json",
        )
        refresh = response.json()["refresh"]

        response = self.client.post(
            "/api/auth/refresh",
            data=json.dumps({"refresh": refresh}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())

    def test_refresh_rejects_an_access_token(self):
        """Los dos tokens se firman igual: lo que los distingue es el campo
        type, y por eso el refresh no acepta un access."""
        access = self._login("diana@docentes.edu.ar", "Docente12345!")

        response = self.client.post(
            "/api/auth/refresh",
            data=json.dumps({"refresh": access}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    def test_admin_role_becomes_staff_on_save(self):
        user = self.user_model.objects.create_user(
            email="jefa@plataforma.edu.ar",
            password="Clave12345!",
            first_name="Julia",
            last_name="Jefa",
            role=UserRole.ADMIN,
        )
        self.assertTrue(user.is_staff)

    def test_new_account_defaults_to_teacher(self):
        """El unico alta abierta es la del docente, asi que es el default."""
        user = self.user_model.objects.create_user(
            email="sin.rol@docentes.edu.ar",
            password="Clave12345!",
            first_name="Sin",
            last_name="Rol",
        )
        self.assertEqual(user.role, UserRole.TEACHER)

    def test_teacher_can_register_without_token(self):
        """El registro del docente es publico: la cuenta sola no habilita nada."""
        response = self.client.post(
            "/api/auth/register/teacher",
            data=json.dumps(
                {
                    "email": "dario@docentes.edu.ar",
                    "first_name": "Dario",
                    "last_name": "Docente",
                    "password": "Docente12345!",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], UserRole.TEACHER)

    def test_teacher_registration_rejects_duplicated_email(self):
        response = self.client.post(
            "/api/auth/register/teacher",
            data=json.dumps(
                {
                    "email": "diana@docentes.edu.ar",
                    "first_name": "Diana",
                    "last_name": "Repetida",
                    "password": "Docente12345!",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    def test_admin_manages_users_and_others_cannot(self):
        access = self._login("admin@plataforma.edu.ar", "Admin12345!")
        response = self.client.post(
            "/api/admin/users",
            data=json.dumps(
                {
                    "email": "rectorado@iftsX.edu.ar",
                    "first_name": "Ines",
                    "last_name": "Instituto",
                    "password": "Instituto12345!",
                    "role": UserRole.INSTITUTION,
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], UserRole.INSTITUTION)

        teacher_access = self._login("diana@docentes.edu.ar", "Docente12345!")
        response = self.client.get(
            "/api/admin/users",
            HTTP_AUTHORIZATION=f"Bearer {teacher_access}",
        )
        # 403 y no 401: la API sabe quien es, pero el rol no alcanza.
        self.assertEqual(response.status_code, 403)

    def test_admin_cannot_assign_a_role_that_no_longer_exists(self):
        """STUDENT y COMPANY se fueron con el recorte: el service valida contra
        UserRole y no deja entrar un rol viejo por la API."""
        access = self._login("admin@plataforma.edu.ar", "Admin12345!")

        response = self.client.post(
            "/api/admin/users",
            data=json.dumps(
                {
                    "email": "ana@alumnos.edu.ar",
                    "first_name": "Ana",
                    "last_name": "Gomez",
                    "password": "Alumna12345!",
                    "role": "STUDENT",
                }
            ),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(self.user_model.objects.filter(email="ana@alumnos.edu.ar").exists())

    def test_me_returns_the_user_of_the_token(self):
        access = self._login("diana@docentes.edu.ar", "Docente12345!")

        response = self.client.get(
            "/api/auth/me",
            HTTP_AUTHORIZATION=f"Bearer {access}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "diana@docentes.edu.ar")

    def test_me_requires_token(self):
        response = self.client.get("/api/auth/me")
        self.assertEqual(response.status_code, 401)