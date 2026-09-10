FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

# 1. Copiar archivos de configuración
COPY pyproject.toml uv.lock ./

# 2. Instalar ÚNICAMENTE las dependencias (evita compilar el proyecto antes de copiar src/)
RUN uv sync --frozen --no-cache --no-install-project

# 3. Copiar el código fuente
COPY . .

# 4. Sincronizar e instalar el proyecto completo (ahora que src/backend ya existe)
RUN uv sync --frozen --no-cache

ENV PYTHONPATH=/app/src

CMD ["uv", "run", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "80"]