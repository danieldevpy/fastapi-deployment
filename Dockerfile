FROM python:3.12.9-slim

RUN apt-get update && apt-get install -y git

WORKDIR /app/src

COPY /src .

RUN pip install -r requirements.txt

CMD [ "uvicorn", "main:app" , "--host", "0.0.0.0", "--port", "8005"]