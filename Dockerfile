FROM python:3.7-slim
WORKDIR /app
RUN pip install gunicorn

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY ./ ./

CMD gunicorn --workers 1 --bind 0.0.0.0:80 web:app



