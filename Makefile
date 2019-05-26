all: script docs

help:
	@printf 'Supported targets:\n\n'
	@printf '     all: Alias for "script" and "docs"\n'
	@printf '  script: Generates mmh script with default options\n'
	@printf '    docs: Builds documentation in "doc" sub directory\n'
	@printf '   clean: Cleans up generated files from source tree\n\n'

script: mmh

docs:
	$(MAKE) -C doc all

clean:
	rm -f *~ '#'*
	rm -f mmh
	$(MAKE) -C doc clean

mmh: mmh.in
	./configure

.PHONY: all clean docs help script
