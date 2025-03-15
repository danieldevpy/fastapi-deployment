FROM python:3.12.9-slim

WORKDIR /app/src

COPY /src .

RUN pip install -r requirements.txt

CMD [ "uvicorn", "main:app" ]