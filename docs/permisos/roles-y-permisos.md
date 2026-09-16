# Roles y permisos — ORI Manager

## Resumen

- Los **roles** y **permisos** se definen **en código**, en `backend/src/backend/core/permisos.py`.
- En la base de datos solo se guarda **el rol de cada usuario** (columna `users.rol`). No existen tablas de roles ni de permisos.
- Los endpoints autorizan por **permiso**, nunca por rol: `requiere(Permiso.X)`.
- El frontend recibe los permisos del usuario desde `GET /api/auth/me` y solo los usa para **mostrar u ocultar** elementos. La seguridad real está en el backend.

```text
users.rol  ──►  PERMISOS_POR_ROL[rol]  ──►  requiere(Permiso.X) en el router  ──►  401 / 403 / OK
                        │
                        └──►  /api/auth/me → { rol, permisos[] } → useSesion().puede('x') en React
```

## Roles actuales

| Rol (valor en BD) | Nombre visible | Descripción (README, regla 11) |
|---|---|---|
| `administrador` | Administrador | Acceso total: crear, editar y eliminar. |
| `usuario_ori` | Usuario ORI | Ve toda la información en detalle, pero no crea, edita ni elimina. |
| — | Invitado | **No es un rol almacenado.** Es cualquier petición sin sesión. Solo accede a endpoints públicos (p. ej. consultar si existe un convenio con una entidad). |

## Matriz de permisos

| Permiso | Administrador | Usuario ORI |
|---|:-:|:-:|
| `usuarios.gestionar` — listar, crear y editar usuarios (incluye rol y estado) | ✅ | ❌ |
| `aliados.ver` | ✅ | ✅ |
| `aliados.gestionar` — crear, editar, inactivar | ✅ | ❌ |
| `convenios.ver` — detalle, historial, documentos | ✅ | ✅ |
| `convenios.gestionar` — crear, etapas, firmas, evaluación, renovación | ✅ | ❌ |

## Cómo está en la base de datos

Tabla `users` (migración `b7e1c4a9d2f3_add_rol_to_users`):

| Columna | Tipo | Detalle |
|---|---|---|
| `rol` | `VARCHAR(30) NOT NULL` | `DEFAULT 'usuario_ori'` |

Restricción:

```sql
CONSTRAINT ck_users_rol CHECK (rol IN ('administrador', 'usuario_ori'))
```

- El `DEFAULT` hace que todo usuario nuevo o preexistente arranque con el **mínimo privilegio**.
- El `CHECK` impide guardar un rol que no exista en el código, aunque se escriba directamente por SQL.
- Se usa `VARCHAR + CHECK` en lugar de un `ENUM` nativo de Postgres porque cambiar un `ENUM` en Alembic es incómodo; un `CHECK` se reemplaza en dos líneas.
- En el modelo (`models/user.py`) la columna es `Mapped[Rol]`: SQLAlchemy convierte automáticamente entre el texto de la BD y el enum de Python.

El rol se lee de la base de datos **en cada petición** (a través de la sesión), así que un cambio de rol o una desactivación aplica de inmediato, sin cerrar sesiones.

Consultas útiles:

```sql
-- Usuarios por rol
SELECT rol, count(*) FROM users GROUP BY rol;

-- Administradores activos
SELECT email FROM users WHERE rol = 'administrador' AND is_active;
```

## `permisos.py`

```python
class Rol(StrEnum):
    ADMINISTRADOR = "administrador"
    USUARIO_ORI = "usuario_ori"


class Permiso(StrEnum):
    USUARIOS_GESTIONAR = "usuarios.gestionar"
    ALIADOS_VER = "aliados.ver"
    ALIADOS_GESTIONAR = "aliados.gestionar"
    CONVENIOS_VER = "convenios.ver"
    CONVENIOS_GESTIONAR = "convenios.gestionar"


PERMISOS_POR_ROL: dict[Rol, frozenset[Permiso]] = {
    Rol.ADMINISTRADOR: frozenset(Permiso),          # todos los permisos, incluidos los futuros
    Rol.USUARIO_ORI: frozenset({Permiso.ALIADOS_VER, Permiso.CONVENIOS_VER}),
}
```

Convención de nombres de permiso: `<recurso>.ver` y `<recurso>.gestionar`. Solo se divide un permiso (p. ej. `convenios.firmar`) cuando exista un rol que necesite tener una parte y no la otra.

## Proteger un endpoint

```python
from typing import Annotated

from backend.api.deps import requiere
from backend.core.permisos import Permiso
from backend.models.user import User

# Si no necesitas al usuario:
@router.get("", dependencies=[requiere(Permiso.ALIADOS_VER)])
def listar_aliados(db: DatabaseSession): ...

# Si necesitas al usuario autenticado:
@router.post("")
def crear_aliado(datos: AliadoCrear, db: DatabaseSession,
                 usuario: Annotated[User, requiere(Permiso.ALIADOS_GESTIONAR)]): ...
```

Respuestas: sin sesión o sesión inválida → **401**; usuario inactivo → **403**; sin el permiso → **403**.

Reglas:

- **Todo endpoint nuevo debe declarar `requiere(...)`.** El test `tests/test_permisos.py::test_rutas_no_publicas_exigen_sesion` falla si una ruta no exige sesión.
- Un endpoint público (Invitado) **no** lleva `requiere(...)` y debe agregarse a `RUTAS_PUBLICAS` en ese test, dejando claro que es intencional.
- Los servicios **no** reciben el rol ni validan permisos: la autorización se hace una sola vez, en el router.
- Nunca escribas `if usuario.rol == Rol.ADMINISTRADOR`. Pregunta por el permiso.

## Usar permisos en el frontend

```tsx
import { useSesion } from '../auth/sesion'

const { sesion, puede } = useSesion()   // sesion === null → Invitado
{puede('aliados.gestionar') && <button className="btn btn-primary">Nuevo aliado</button>}
```

Proteger una ruta en `frontend/src/app/router.tsx`:

```tsx
{
  element: <RequierePermiso permiso="aliados.ver" />,
  children: [{ path: '/aliados', element: <AliadosPage /> }],
}
```

`RequierePermiso` redirige a `/login` si no hay sesión y muestra "Acceso denegado" si falta el permiso.

## Agregar un permiso nuevo

No requiere migración.

1. **Backend** — `core/permisos.py`: agregar el valor al enum `Permiso` y asignarlo a los roles que lo tengan en `PERMISOS_POR_ROL` (el Administrador lo recibe automáticamente).
2. **Backend** — proteger los endpoints con `requiere(Permiso.NUEVO)`.
3. **Frontend** — `src/auth/sesion.ts`: agregar el mismo texto al tipo `Permiso`.
4. **Frontend** — usar `puede('nuevo.permiso')` / `RequierePermiso` donde corresponda.
5. **Tests** — un caso 403 para el rol sin permiso y un caso OK para el rol con permiso.
6. Actualizar la matriz de este documento.

## Agregar un rol nuevo

Ejemplo: `coordinador`.

1. **Backend** — `core/permisos.py`: agregar `COORDINADOR = "coordinador"` a `Rol` y su entrada en `PERMISOS_POR_ROL`. Si olvidas la entrada, `tests/test_permisos.py::test_todo_rol_tiene_permisos_definidos` falla.
2. **Migración** — el `CHECK` de la BD **no se actualiza solo** (Alembic autogenerate no detecta cambios en restricciones `CHECK`). Crea la revisión a mano:

   ```bash
   cd backend
   uv run alembic revision -m "add rol coordinador"
   ```

   ```python
   def upgrade() -> None:
       op.drop_constraint('ck_users_rol', 'users', type_='check')
       op.create_check_constraint(
           'ck_users_rol', 'users', "rol IN ('administrador', 'usuario_ori', 'coordinador')"
       )


   def downgrade() -> None:
       op.execute("UPDATE users SET rol = 'usuario_ori' WHERE rol = 'coordinador'")
       op.drop_constraint('ck_users_rol', 'users', type_='check')
       op.create_check_constraint(
           'ck_users_rol', 'users', "rol IN ('administrador', 'usuario_ori')"
       )
   ```

   El valor del rol debe tener máximo 30 caracteres.
3. **Frontend** — `src/auth/sesion.ts`: agregar el valor al tipo `Rol` y su nombre visible en `ETIQUETAS_ROL`. TypeScript marcará error si falta la etiqueta. Los selects de rol toman las opciones de `ETIQUETAS_ROL`, así que aparece solo en el modal de usuarios.
4. **Tests** — casos de permisos para el nuevo rol.
5. Aplicar la migración en cada ambiente con el rol administrativo de BD (ver `docs/operations/supabase.md`) y actualizar este documento.

## Quitar o renombrar un rol

1. Migración que primero **reasigne** a los usuarios afectados (`UPDATE users SET rol = '...' WHERE rol = '...'`) y luego reemplace el `CHECK`.
2. Quitar/renombrar el valor en `Rol`, `PERMISOS_POR_ROL`, el tipo `Rol` y `ETIQUETAS_ROL` del frontend.
3. Nunca dejes el sistema sin ningún `administrador`.

## Gestión de roles desde la aplicación

Sección **Usuarios** (`/admin/usuarios`), visible solo con `usuarios.gestionar`:

- **Nuevo usuario**: correo, contraseña (8–72 bytes) y rol.
- **Editar**: correo, nueva contraseña (opcional), rol y estado.

API equivalente:

| Método | Ruta | Permiso |
|---|---|---|
| `GET` | `/api/usuarios` | `usuarios.gestionar` |
| `POST` | `/api/usuarios` | `usuarios.gestionar` |
| `PATCH` | `/api/usuarios/{id}` | `usuarios.gestionar` |

**Regla de protección:** un administrador no puede cambiar su propio rol ni desactivarse (responde 409). Como solo un administrador puede gestionar usuarios, siempre queda al menos uno activo. Para el primer administrador o para recuperar el acceso, usa el CLI descrito en [`docs/users/crear-admin.md`](../users/crear-admin.md).
