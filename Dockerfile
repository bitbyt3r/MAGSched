FROM python:alpine

RUN pip install --upgrade flask redis requests google-api-python-client google-auth-httplib2 google-auth-oauthlib gunicorn

ADD backends/ backends/
ADD templates/ templates/
ADD cache_loader.py cache_loader.py
ADD config.py config.py
ADD database.py database.py
ADD frontend.py frontend.py
ADD entrypoint.sh entrypoint.sh

ENV BACKENDS="[]"
ENV REDIS_HOST="localhost"
ENV REDIS_PORT="6379"
ENV REDIS_DB="0"
ENV REFRESH_DELAY="60"

EXPOSE 8080

CMD /bin/sh entrypoint.sh
