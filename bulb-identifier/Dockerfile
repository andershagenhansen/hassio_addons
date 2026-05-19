ARG BUILD_FROM
FROM $BUILD_FROM

WORKDIR /app

COPY app/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY app/ .

COPY run.sh /run.sh
RUN chmod +x /run.sh

CMD ["/run.sh"]
