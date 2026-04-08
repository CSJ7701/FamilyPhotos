FROM python:3.11-slim

WORKDIR /code

# Prevent python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE 1
ENV PTHONUNBUFFERED 1

# Install dependencies
# RUN apt-get update &&

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
