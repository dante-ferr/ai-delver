ENTRYPOINT ?= main

prepare-scripts:
	chmod +x run.sh

on-run: prepare-scripts

run: on-run
	./run.sh $(ENTRYPOINT)