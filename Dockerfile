FROM python:3.6-slim

ENV WORKDIR /home/app
WORKDIR $WORKDIR

RUN apt-get update \
 && apt-get install --no-install-recommends --no-install-suggests -y apt-utils \
 && apt-get install --no-install-recommends --no-install-suggests -y gcc bzip2 git curl nginx libpq-dev gettext \
    libgdal-dev python3-cffi python3-gdal vim

RUN pip install -U pip==20.2.2 setuptools==49.6.0
RUN pip install pipenv==2018.11.26
RUN pip install gunicorn==19.9.0
RUN pip install gevent==1.4.0
RUN pip install psycopg2-binary
RUN apt-get install -y libjpeg-dev libgpgme-dev linux-libc-dev musl-dev libffi-dev libssl-dev
ENV LIBRARY_PATH=/lib:/usr/lib

COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

RUN pipenv install --system

COPY . .

RUN git clone https://github.com/Ilhasoft/weni-protobuffers weni/protos/flow/
RUN python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/inteligence/authentication.proto
RUN python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/inteligence/organization.proto
RUN python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/rapidpro_billing/billing.proto
RUN python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/rapidpro_flow/flow.proto
RUN python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/rapidpro_org/org.proto
RUN python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/rapidpro_statistic/statistic.proto
RUN python -m grpc_tools.protoc --experimental_allow_proto3_optional --proto_path=./ --python_out=./ --grpc_python_out=./ ./weni/protos/flow/rapidpro_user/user.proto

RUN chmod +x ./entrypoint.sh
ENTRYPOINT [ "./entrypoint.sh" ]
