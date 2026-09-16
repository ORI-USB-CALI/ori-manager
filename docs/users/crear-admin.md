# CLI: crear el primer administrador

## Para qué sirve

Solo un administrador puede crear usuarios y asignar roles desde la aplicación. En una base de datos nueva no hay ninguno, así que el primero se crea con este comando:

```bash
uv run python -m backend.scripts.crear_admin --email admin@usb.edu.co
```

Código: `backend/src/backend/scripts/crear_admin.py`.

## Qué hace

| Situación | Resultado |
|---|---|
| El correo **no existe** | Pide la contraseña y crea el usuario con rol `administrador`, activo. Imprime `Administrador creado: <correo>`. |
| El correo **ya existe** | **No pide contraseña ni la cambia.** Lo promueve a `administrador` y lo reactiva si estaba inactivo. Imprime `Administrador promovido: <correo>`. |

- Se puede ejecutar varias veces sin duplicar usuarios.
- La contraseña se pide de forma oculta (no queda en el historial de la terminal ni en variables de entorno).
- Regla de contraseña: entre **8 y 72 bytes** (límite de bcrypt), la misma que aplica la API.
- Solo hace `SELECT`, `INSERT` y `UPDATE`, así que funciona con el rol de runtime de la BD; no necesita el rol administrativo.
- Requiere que las migraciones estén aplicadas (`uv run alembic upgrade head`).

## Uso

### Con Docker Compose (stack completo)

```bash
docker compose up -d
docker compose exec backend uv run python -m backend.scripts.crear_admin --email admin@usb.edu.co
```

Luego entra a http://localhost:5173/login.

### Dentro del devcontainer o en local

Desde `backend/`, con `backend/.env` configurado:

```bash
cd backend
uv run alembic upgrade head
uv run python -m backend.scripts.crear_admin --email admin@usb.edu.co
```

### Ambientes en la nube (Staging / Production)

La conexión se configura con las mismas variables `DATABASE_*` que usa el backend (ver `docs/operations/supabase.md`). Opciones:

- **Desde tu máquina** (o el devcontainer), exportando temporalmente las variables del ambiente destino y ejecutando el comando desde `backend/`:

  ```bash
  export DATABASE_HOST=<session-pooler-host> DATABASE_PORT=5432 DATABASE_NAME=postgres \
         DATABASE_USER=<usuario> DATABASE_SSLMODE=require
  read -rs DATABASE_PASSWORD && export DATABASE_PASSWORD   # no queda en el historial
  uv run python -m backend.scripts.crear_admin --email admin@usb.edu.co
  ```

  No guardes esas credenciales en archivos del repositorio.

- **Desde la Shell del servicio backend en Render**, que ya tiene las variables configuradas. Solo está disponible en planes pagos; los servicios de `render.yaml` usan `plan: free`.

## Probar roles: crear un usuario normal

Después del primer administrador, el resto de usuarios se crea desde la aplicación:

1. Inicia sesión como administrador.
2. Ve a **Usuarios** → **Nuevo usuario**.
3. Ingresa correo, contraseña y rol **Usuario ORI**.

## Recuperar el acceso

Si ningún administrador puede entrar (contraseña olvidada, usuario desactivado por SQL, etc.), ejecuta el comando con el correo de un usuario existente: queda como administrador activo. El comando **no** restablece contraseñas; para eso, otro administrador puede editar el usuario desde la aplicación, o crea un administrador nuevo con otro correo y cambia la contraseña desde **Usuarios** → **Editar**.

## Errores comunes

| Mensaje | Causa / solución |
|---|---|
| `La contraseña debe tener entre 8 y 72 bytes` | Ingresa una contraseña válida y vuelve a ejecutar. |
| `relation "users" does not exist` / `column users.rol does not exist` | Faltan migraciones: `uv run alembic upgrade head`. |
| `connection refused` / `could not translate host name "db"` | La base de datos no está arriba o las variables `DATABASE_*` apuntan a otro host. Con Compose, ejecútalo dentro del contenedor `backend`. |
| `Warning: Password input may be echoed.` | Se ejecutó sin terminal interactiva (p. ej. con `-T` o una tubería). Ejecútalo en una terminal interactiva. |
