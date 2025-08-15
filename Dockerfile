FROM python:3-alpine

WORKDIR /usr/src/app

# Get all of the Python files
COPY --chmod=0755 . .

# Instal dependencies
RUN pip install --no-cache-dir requests

VOLUME /usr/src/app/images

CMD ["python", "-OO", "main.py"]