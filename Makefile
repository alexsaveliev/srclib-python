.PHONY: install

install:
	@mkdir -p .bin
	go build -o .bin/srclib-python
	sudo pip install . --upgrade

# TODO: virtualenv, pip
