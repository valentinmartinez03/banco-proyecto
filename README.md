# CampusLab — Banco de Proyectos Académicos

> **API REST** construida con **Django 6** y **Django Ninja** para centralizar, gestionar y publicar proyectos académicos realizados por alumnos en sus cursadas universitarias o terciarias.

---

## 📌 Descripción del Proyecto

**CampusLab** funciona como una vitrina institucional y catálogo público de proyectos académicos. Permite que las instituciones educativas organicen sus carreras y docentes; los docentes gestionen sus comisiones (cursadas), inscriban alumnos y carguen los proyectos realizados con sus tecnologías, imágenes, documentación y repositorios; y las instituciones revisen y aprueben los trabajos antes de que sean visibles públicamente.

Cualquier persona puede navegar y buscar en el catálogo público sin necesidad de iniciar sesión.

---

## 🚀 Tecnologías Utilizadas

- **Framework Web**: [Django 6.0](https://www.djangoproject.com/)
- **Capa de API**: [Django Ninja 1.6](https://django-ninja.dev/) *(rápido, tipado con Pydantic y documentación interactiva automática)*
- **Autenticación**: JWT (JSON Web Tokens) con [PyJWT](https://pyjwt.readthedocs.io/) *(Access y Refresh Tokens)*
- **Base de Datos**: SQLite *(fácil portabilidad a PostgreSQL via variables de entorno)*
- **Gestión de Archivos e Imágenes**: Django `FileField` + [Pillow](https://python-pillow.org/)
- **Entorno y Configuración**: `python-dotenv`

---

## 👥 Actores y Roles del Sistema

El sistema implementa control de acceso basado en roles (RBAC) y validaciones a nivel de objeto:

| Rol | Descripción |
|---|---|
| **ADMIN** | Administrador de la plataforma. Da de alta instituciones, gestiona usuarios y administra catálogos globales (tecnologías). |
| **INSTITUTION** | Cuenta de una institución educativa. Invita docentes, acepta solicitudes de vinculación, administra carreras y revisa/aprueba proyectos para el catálogo. |
| **TEACHER** | Docente. Crea sus cursadas, inscribe a sus alumnos y sube los proyectos de sus comisiones. |
| *(Alumnos)* | **No requieren cuenta ni login**. Son cargados como datos por el docente dentro de la institución y asociados a los proyectos que integraron. |

---

## 🏗️ Arquitectura y Patrones de Diseño

El proyecto sigue una estricta **arquitectura en capas por responsabilidad**, desacoplando la lógica HTTP de las reglas del negocio y la base de datos:

```text
       HTTP Request
            │
            ▼
        api.py         ◄── Permisos, validación de entrada/salida (Schemas) y traducción de errores HTTP.
       ┌────┴────┐
       ▼         ▼
 selectors.py  services.py ◄── Lógica de negocio pura, reglas del dominio y transacciones atómicas.
  (Lectura)   (Escritura)
       └────┬────┘
            ▼
        models.py      ◄── Estructura de tablas, relaciones y constraints de integridad.
        managers.py    ◄── QuerySets encapsulados y filtros encadenables reutilizables.
```

> **Regla de oro del proyecto**: Los archivos `api.py` **nunca** realizan consultas directas (`.filter()`, `.create()`) a la base de datos. Solo delegan en *selectors* o *services*.

---

## 📁 Estructura del Repositorio

```text
banco-proyecto/
├── CampusLab/                # Configuración global del proyecto Django
│   ├── settings.py           # Variables, JWT, apps instaladas y base de datos
│   ├── api.py                # Instancia central de NinjaAPI y montaje de routers
│   ├── urls.py               # Enrutador raíz (/admin/, /api/, archivos media)
│   ├── wsgi.py / asgi.py     # Entrypoints de servidor
│
├── core/                     # Módulos transversales y utilitarios
│   ├── auth.py               # Autenticación JWTAuth y RoleAuth para Django Ninja
│   ├── jwt.py                # Generación, firma y decodificación de tokens JWT
│   └── errors.py             # Adaptador de ValidationError a HTTP 400
│
├── apps/
│   ├── accounts/             # Usuario custom (email login), roles, login y refresh
│   ├── institutions/         # Instituciones educativas, reglas de email y membresías docentes
│   ├── academics/            # Carreras, cursadas (comisiones), alumnos e inscripciones
│   ├── catalogs/             # Catálogo controlado de Tecnologías (React, Python, etc.)
│   └── projects/             # Proyectos, participantes, tecnologías, assets (imágenes/docs) y links
│
├── data/                     # Directorio de persistencia para SQLite
├── media/                    # Archivos subidos (imágenes y documentos de proyectos)
├── manage.py
├── requirements.txt
└── .env.example              # Plantilla de variables de entorno
```

---

## ⚙️ Instalación y Puesta en Marcha

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/banco-proyecto.git
cd banco-proyecto
```

### 2. Crear y activar un entorno virtual

En **Windows (PowerShell)**:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

En **Linux / macOS**:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar las dependencias

```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno

Copia el archivo `.env.example` como `.env`:

```bash
# En Windows:
copy .env.example .env

# En Linux/macOS:
cp .env.example .env
```

*(Opcional)* Edita el archivo `.env` para ajustar claves secretas o configuración de desarrollo.

### 5. Ejecutar migraciones

```bash
python manage.py migrate
```

### 6. Crear el usuario Administrador

```bash
python manage.py createsuperuser
```
*(Ingresa email, nombre, apellido y contraseña)*.

### 7. Iniciar el servidor de desarrollo

```bash
python manage.py runserver
```

El servidor estará corriendo en: `http://127.0.0.1:8000/`

---

## 📖 Documentación Interactiva (Swagger / OpenAPI)

Gracias a Django Ninja, la documentación interactiva de la API está disponible de forma nativa sin configuración adicional:

- **Swagger UI**: [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)
- **Django Admin**: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)
- **Health Check**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## 🛣️ Resumen de Endpoints de la API

### 🌐 Públicos (sin autenticación)
- `POST /api/auth/login` — Autenticación de usuarios, retorna par de tokens JWT.
- `POST /api/auth/refresh` — Renovación de access token mediante refresh token.
- `POST /api/auth/register/teacher` — Registro público de docentes.
- `POST /api/institutions/activate` — Primer acceso y activación de cuenta institucional habilitada.
- `GET /api/projects` — Catálogo público de proyectos aprobados (con múltiples filtros combinables).
- `GET /api/projects/{slug}` — Ficha detallada de un proyecto aprobado.
- `GET /api/institutions` — Listado de instituciones educativas.
- `GET /api/careers` — Listado de carreras universitarias/terciarias.
- `GET /api/technologies` — Listado de tecnologías disponibles.

### 👨‍🏫 Docente (`/api/teacher`) — Requiere Rol `TEACHER`
- `GET /api/teacher/memberships` — Lista de relaciones con instituciones.
- `POST /api/teacher/memberships` — Solicitar ingreso a una institución.
- `POST /api/teacher/memberships/{id}/accept|reject` — Responder invitaciones de instituciones.
- `GET /api/teacher/courses` — Cursadas que dicta el docente.
- `POST /api/teacher/courses` — Crear una nueva cursada.
- `GET|POST /api/teacher/courses/{id}/students` — Listar o inscribir alumnos en la cursada.
- `GET|POST /api/teacher/projects` — Listar y cargar proyectos de sus cursadas.
- `POST /api/teacher/projects/{id}/assets` — Subir imágenes o documentos (multipart/form-data).
- `POST /api/teacher/projects/{id}/links` — Agregar links externos (GitHub, demos, videos).

### 🏛️ Institución (`/api/institution`) — Requiere Rol `INSTITUTION`
- `GET /api/institution/teachers` — Listado de docentes vinculados.
- `POST /api/institution/teachers/invite` — Invitar a un docente por email.
- `POST /api/institution/teachers/{id}/accept|reject` — Aceptar o rechazar solicitudes de docentes.
- `PUT /api/institution/teachers/{id}/publishing` — Conceder o revocar el privilegio de publicar sin revisión previa.
- `GET|POST /api/institution/careers` — Listar y dar de alta carreras.
- `GET /api/institution/projects` — Bandeja de revisión de proyectos de sus carreras.
- `POST /api/institution/projects/{id}/approve` — Aprobar proyecto para el catálogo público.
- `POST /api/institution/projects/{id}/request-changes` — Devolver proyecto con devolución escrita para correcciones.
- `POST /api/institution/projects/{id}/reject` — Rechazar proyecto.

---

## 🔒 Variables de Entorno

| Variable | Tipo | Default | Descripción |
|---|---|---|---|
| `SECRET_KEY` | string | *default inseguro* | Clave criptográfica de Django |
| `JWT_SECRET_KEY` | string | *default inseguro* | Clave secreta para la firma de tokens JWT |
| `ACCESS_TOKEN_MINUTES` | int | `60` | Tiempo de vida del access token |
| `REFRESH_TOKEN_DAYS` | int | `7` | Tiempo de vida del refresh token |
| `DEBUG` | bool | `True` | Modo debug de Django |
| `ALLOWED_HOSTS` | string | `localhost,127.0.0.1` | Hosts permitidos separados por comas |
| `SQLITE_PATH` | path | `data/db.sqlite3` | Ruta física de la base de datos SQLite |
| `EMAIL_BACKEND` | string | `console.EmailBackend` | Backend de correos electrónicos |
