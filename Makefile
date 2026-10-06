test:
	python3 -m unittest discover -s tests -v

demo:
	python3 -m atlas ingest examples/documents
	python3 -m atlas serve

eval:
	python3 -m atlas ingest examples/documents
	python3 -m atlas eval
