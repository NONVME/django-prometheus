FROM python:3.11 as builder

WORKDIR /usr/app/src
ARG POETRY_VER=1.4.0

RUN apt-get update && apt-get install -y \
    gcc \
    vim \
    gdal-bin \
    libgdal-dev \
    python3-gdal \
    && rm -rf /var/lib/apt/lists/*

# Don't buffer `stdout`:
ENV PYTHONUNBUFFERED=1
# Don't create `.pyc` files:
ENV PYTHONDONTWRITEBYTECODE=1

# Установка переменных окружения для GDAL
ENV CPLUS_INCLUDE_PATH=/usr/include/gdal
ENV C_INCLUDE_PATH=/usr/include/gdal

ENV POETRY_HOME=/opt/poetry
ENV POETRY_VIRTUALENVS_IN_PROJECT=true
ENV PATH="$POETRY_HOME/bin:$PATH"

# Установка Poetry
RUN python3 -c 'from urllib.request import urlopen; print(urlopen("https://install.python-poetry.org").read().decode())' | python3 - --version ${POETRY_VER}

# Копируем сначала все файлы проекта
COPY . /usr/app/src/

# Затем устанавливаем зависимости
RUN poetry install --only main --no-ansi

EXPOSE 8000

# CMD ["poetry", "run", "python3", "django_prometheus/tests/end2end/manage.py", "runserver", "0.0.0.0:8000"]
