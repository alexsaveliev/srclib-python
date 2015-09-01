.PHONY: install install-docker update-dockerfile

all: install update-dockerfile

.env:
	bash ./install_env.sh
install: .env
	@mkdir -p .bin
	go get -d ./...
	go build -o .bin/srclib-python

	.env/bin/pip install -r requirements.txt --upgrade
	.env/bin/pip install . --upgrade

update-dockerfile:
	src toolchain build sourcegraph.com/sourcegraph/srclib-python

install-docker:
	go install .
	pip install -r requirements.txt --upgrade
	pip install . --upgrade
