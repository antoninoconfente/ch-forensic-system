# Despliegue en producción — CH Curiosities Hunter

Contenedor NiceGUI + PostgreSQL/Supabase. La interfaz y la lógica de negocio no requieren cambios entre entornos; solo variables de entorno y secretos.

## Variables de entorno obligatorias

| Variable | Descripción |
|----------|-------------|
| `ENV` | Debe ser `production` en contenedor/cloud. |
| `PORT` | Puerto HTTP interno (por defecto `8080`). |
| `SUPABASE_URL` | URL del proyecto Supabase. |
| `SUPABASE_KEY` | Clave pública (anon) para Auth del cliente. |
| `SUPABASE_SECRET_KEY` | Clave de servicio (storage/operaciones server-side). |
| `DATABASE_URL` | PostgreSQL (p. ej. Supabase pooler `postgresql://...`). |
| `GEMINI_API_KEY` | API de visión / multimodal del consejo de expertos. |
| `SERPAPI_API_KEY` | Búsqueda visual y señales de mercado (capa 2). |
| `NICEGUI_STORAGE_SECRET` | Secreto para firmar `app.storage.user` (sesiones). Usar valor aleatorio largo en producción. |
| `CH_INVITE_CODE` | Código de invitación para registro en `/login`. |
| `ADMIN_EMAIL` | Email que recibe rol `admin` al registrarse (además del primer usuario). |
| `AUTH_BYPASS_LOCAL` | **Debe ser `false` en producción.** |

Opcionales habituales:

- `OPENAI_API_KEY` — si usas rutas OpenAI en investigación.
- `SUPABASE_BUCKET` — bucket de evidencias (default `evidence`).

Nunca incluyas `.env` en la imagen Docker ni en el repositorio.

## Comprobación de salud

- **Ruta:** `GET /health`
- **Respuesta:** `{"status": "ok", "service": "ch-curiosities-hunter"}`
- No requiere sesión; sirve para balanceadores y `HEALTHCHECK` del Dockerfile.

## Construir y probar en local

```bash
docker build -t ch-curiosities-hunter:latest .

docker run --rm -p 8080:8080 \
  -e ENV=production \
  -e PORT=8080 \
  -e AUTH_BYPASS_LOCAL=false \
  -e NICEGUI_STORAGE_SECRET="$(openssl rand -hex 32)" \
  -e SUPABASE_URL="https://YOUR_PROJECT.supabase.co" \
  -e SUPABASE_KEY="your-anon-key" \
  -e SUPABASE_SECRET_KEY="your-service-key" \
  -e DATABASE_URL="postgresql+psycopg2://..." \
  -e GEMINI_API_KEY="..." \
  -e SERPAPI_API_KEY="..." \
  -e CH_INVITE_CODE="CH-ARCHIVE-2026" \
  -e ADMIN_EMAIL="curator@example.com" \
  ch-curiosities-hunter:latest
```

Verificar:

```bash
curl -s http://localhost:8080/health
```

Abrir la aplicación en `http://localhost:8080/login`.

## Despliegue en nube (patrón general)

1. **Registro de imagen** — push a GHCR, ECR, Artifact Registry o registry del proveedor (`docker tag` + `docker push`).
2. **Servicio gestionado** — Cloud Run, ECS/Fargate, App Runner, Fly.io, Railway, etc.:
   - Puerto del contenedor: `8080` (o alinear `PORT` con el que expone la plataforma).
   - Health check HTTP en `/health`, intervalo 30 s.
   - CPU/memoria según carga de investigaciones (mínimo recomendado: 1 vCPU, 1–2 GiB RAM).
3. **Secretos** — inyectar variables anteriores como secretos del proveedor, no como literales en la imagen.
4. **Base de datos** — `DATABASE_URL` con SSL; ejecutar migraciones/`init_db` según tu pipeline antes del primer tráfico.
5. **HTTPS** — terminar TLS en el balanceador; el contenedor escucha HTTP en `0.0.0.0`.
6. **Persistencia** — expedientes y evidencias viven en Supabase/PostgreSQL y storage; `data/temp` es efímero dentro del contenedor.

## Desarrollo vs producción

| | Desarrollo | Producción (`ENV=production`) |
|--|------------|-------------------------------|
| `host` | `0.0.0.0` | `0.0.0.0` |
| `reload` | `true` (si no es production) | `false` |
| `show` | `true` | `false` |
| Auth | según `.env` | `AUTH_BYPASS_LOCAL=false` obligatorio |

Arranque directo sin Docker:

```bash
export ENV=production
export PORT=8080
python app.py
```