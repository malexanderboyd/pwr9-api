FROM python:3.8-slim
WORKDIR /app
ENV PATH $PATH:/usr/local/gcloud/google-cloud-sdk/bin
RUN curl -sSL https://sdk.cloud.google.com | bash
RUN pip install gunicorn

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY ./ ./

CMD gunicorn --workers 1 --bind 0.0.0.0 web:app



