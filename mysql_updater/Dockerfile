FROM python:3.12-alpine
WORKDIR /app
RUN pip install --no-cache-dir mysql-connector-python
COPY run.py /app/run.py
CMD ["python", "/app/run.py"]
