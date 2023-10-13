FROM python:3.10

WORKDIR /code/src

COPY ./requirements.txt /code/requirements.txt

RUN ulimit -Sn 1000000

RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

RUN pip install git+https://github.com/neptune-ai/neptune-client.git@partitioned

COPY . /code/src
