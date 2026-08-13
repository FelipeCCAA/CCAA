FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN addgroup --system ccaa && adduser --system --ingroup ccaa ccaa

COPY requirements.txt ./
RUN pip install --requirement requirements.txt

COPY --chown=ccaa:ccaa . .

USER ccaa

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--config", "config/gunicorn.conf.py"]
