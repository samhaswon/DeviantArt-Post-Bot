FROM python:3-alpine

ENV PYTHONUNBUFFERED=TRUE

WORKDIR /usr/src/app

# Get all of the Python files
COPY --chmod=0755 . .

# Install dependencies
RUN pip install --no-cache-dir requests

VOLUME ["/usr/src/app/images", "/usr/src/app/posted"]

CMD ["python", "-OO", "main.py"]
