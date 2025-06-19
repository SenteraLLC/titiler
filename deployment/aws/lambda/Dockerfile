ARG PYTHON_VERSION=3.12

FROM --platform=linux/amd64 public.ecr.aws/lambda/python:${PYTHON_VERSION}

WORKDIR /tmp

# Install system dependencies to compile (numexpr)
RUN dnf install -y gcc-c++ && dnf clean all

RUN pip install pip -U
# Install TiTiler from local source. This is necessary because
# pyproject.toml refers to TiTiler dependencies (core, extensions,
# mosaic, and application) that also use filesystem paths.
COPY . /titiler
RUN pip install "/titiler/src/titiler/application" "mangum>=0.10.0" -t /asset --no-binary pydantic

RUN mkdir -p /asset/lib
RUN cp /lib64/libexpat.so.1 /asset/lib/

# Reduce package size and remove useless files
RUN cd /asset && find . -type f -name '*.pyc' | while read f; do n=$(echo $f | sed 's/__pycache__\///' | sed 's/.cpython-[0-9]*//'); cp $f $n; done;
RUN cd /asset && find . -type d -a -name '__pycache__' -print0 | xargs -0 rm -rf
RUN cd /asset && find . -type f -a -name '*.py' -print0 | xargs -0 rm -f
RUN find /asset -type d -a -name 'tests' -print0 | xargs -0 rm -rf
RUN rm -rdf /asset/numpy/doc/ /asset/boto3* /asset/botocore* /asset/bin /asset/geos_license /asset/Misc

COPY deployment/aws/lambda/handler.py /asset/handler.py

CMD ["echo", "hello world"]
