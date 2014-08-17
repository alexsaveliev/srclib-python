FROM ubuntu:14.04

RUN apt-get update -qq
RUN apt-get install -qq curl git mercurial

# Install Go
RUN curl -Lo /tmp/golang.tgz https://storage.googleapis.com/golang/go1.3.linux-amd64.tar.gz
RUN tar -xzf /tmp/golang.tgz -C /usr/local
ENV GOROOT /usr/local/go
ENV GOBIN /usr/local/bin
ENV PATH /usr/local/go/bin:$PATH
ENV GOPATH /srclib

# Install Make
RUN apt-get update -qq && apt-get install -qq make

# Install Python and pip
RUN curl https://raw.githubusercontent.com/pypa/pip/1.5.5/contrib/get-pip.py | python
RUN pip install virtualenv
# Python development headers and other libs that some libraries require to install on Ubuntu
RUN apt-get update -qq && apt-get install -qq python-dev libxslt1-dev libxml2-dev zlib1g-dev

# Create python virtualenv
RUN virtualenv /venv
ENV PATH /venv/bin:$PATH

# Install pydep (TODO: move version dependency to Makefile)
ENV PYDEP_VERSION debfd0e681c3b60e33eec237a4473aed1f767004
RUN pip install git+git://github.com/sourcegraph/pydep.git@$PYDEP_VERSION

# Allow determining whether we're running in Docker
ENV IN_DOCKER_CONTAINER true

# Add this toolchain
RUN echo 66a3c308e_5 > /dev/null
ADD . /srclib/src/sourcegraph.com/sourcegraph/srclib-python/
WORKDIR /srclib/src/sourcegraph.com/sourcegraph/srclib-python
RUN go get -v -d
RUN make install-docker

# Add srclib (unprivileged) user
RUN useradd -ms /bin/bash srclib
RUN mkdir /src
RUN chown -R srclib /src /srclib

# Jedi cache directory permissions
RUN mkdir -p /.cache
RUN chown -R srclib /.cache

# Permissions to read Python third-party libs
RUN chown -R srclib /venv

USER srclib

# Project source code is mounted at src
WORKDIR /src

ENTRYPOINT ["srclib-python"]
