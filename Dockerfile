FROM python:3.10-alpine

WORKDIR /app

RUN apk update && apk add --no-cache ffmpeg

# Python dependencies
COPY requirements.txt ./
RUN pip3 --no-cache-dir install -r requirements.txt

COPY . ./

ENTRYPOINT [ "python3",  "transform.py" ]