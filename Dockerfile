FROM python:3.8-slim
WORKDIR /app
RUN pip install gunicorn

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY ./ ./

CMD gunicorn --workers 3 --bind 0.0.0.0:8002 web:app



