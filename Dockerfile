FROM python:3-alpine AS build-stage

RUN mkdir /svc
WORKDIR /svc
COPY requirements.txt /svc

# Install required apk packages
RUN echo "***** Getting required packages *****" && \
    apk add --no-cache --update  \
    gcc \
    musl-dev \
    linux-headers \
    python3-dev \
    g++ \
    git && \
    pip install --upgrade pip

# Build dependencies
RUN echo "***** Building dependencies *****" && \
    pip wheel requests --wheel-dir=/svc/wheels

FROM python:3-alpine AS application

ENV PYTHONUNBUFFERED=TRUE

# Get build-stage files
COPY --link --from=build-stage /svc /usr/src/app

WORKDIR /usr/src/app

# Get all of the Python files
COPY --chmod=0755 . .

# Instal dependencies
RUN pip install --no-index --find-links=/usr/src/app/wheels requests
RUN pip install --no-cache-dir Pillow

VOLUME /usr/src/app/images

CMD ["python", "main.py"]