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

install: script docs
	install --mode=0755 -d $(DESTDIR)/usr/bin
	install --mode=0755 mmh $(DESTDIR)/usr/bin/mmh
	install --mode=0755 -d $(DESTDIR)/etc/MakeMeHappy
	install --mode=0644 etc/*.yaml $(DESTDIR)/etc/MakeMeHappy
	install --mode=0755 -d $(DESTDIR)/usr/share/MakeMeHappy
	install --mode=0644 data/*.yaml $(DESTDIR)/usr/share/MakeMeHappy
	install --mode=0755 -d $(DESTDIR)/usr/lib/python3/dist-packages/makemehappy
	install --mode=0644 makemehappy/*.py $(DESTDIR)/usr/lib/python3/dist-packages/makemehappy
	install --mode=0755 -d $(DESTDIR)/usr/share/doc/makemehappy
	install --mode=0644 doc/mmh.pdf $(DESTDIR)/usr/share/doc/makemehappy/MakeMeHappy.pdf
	install --mode=0755 -d $(DESTDIR)/usr/share/man/man1
	install --mode=0644 doc/mmh.1 $(DESTDIR)/usr/share/man/man1

package:
	make -f debian/rules generate-orig-tarball && debuild -uc -us

.PHONY: all clean docs help install package script
