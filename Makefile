.PHONY: install install-docker update-dockerfile

ENV_URL_BASE := https://pypi.python.org/packages/source/v/virtualenv
ENV_VERSION := 12.0.7

all: install update-dockerfile

install:
	@mkdir -p .bin
	@mkdir -p .env
	go get -d ./...
	go build -o .bin/srclib-python

	# Setup virtual env.
	curl -O $(ENV_URL_BASE)/virtualenv-$(ENV_VERSION).tar.gz
	tar xzf virtualenv-$(ENV_VERSION).tar.gz
	python2 virtualenv-$(ENV_VERSION)/virtualenv.py .env
	.env/bin/pip install -r requirements.txt --upgrade
	.env/bin/pip install . --upgrade

test-dependencies:
	sudo pip install -r .test.requirements.txt --upgrade

update-dockerfile:
	src toolchain build sourcegraph.com/sourcegraph/srclib-python

install-docker:
	go install .
	pip install -r requirements.txt --upgrade
	pip install . --upgrade
