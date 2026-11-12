FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY external_callout.proto .
RUN python -m grpc_tools.protoc \
    -I. \
    --python_out=. \
    --grpc_python_out=. \
    external_callout.proto

COPY server.py .

EXPOSE 8080
CMD ["python", "-u", "server.py"]
