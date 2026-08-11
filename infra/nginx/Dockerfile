FROM node:24-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
ARG VITE_API_URL=/api/
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM python:3.13-slim-bookworm AS django-static
ENV PYTHONDONTWRITEBYTECODE=1 \
    DJANGO_ENV=development \
    DB_ENGINE=postgresql
WORKDIR /build/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir --requirement requirements.txt
COPY backend/ ./
RUN python manage.py collectstatic --noinput

FROM nginx:1.28-alpine
COPY infra/nginx/nginx.conf /etc/nginx/nginx.conf
COPY --from=frontend-build /build/frontend/dist /usr/share/nginx/html
COPY --from=django-static /build/backend/staticfiles /srv/django-static
EXPOSE 8080
