FROM python:3.8.17-slim-bullseye

COPY . /portal
WORKDIR /portal

RUN pip install -r requirements.txt

ENTRYPOINT ["sh", "/app/entrypoint.sh"]