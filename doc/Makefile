MAN = mmh.1
PDF = mmh.pdf
HTML = mmh.html
INFO = mmh.info

CTOPS = --self-contained --number-sections --toc

TEX_META = -V date='\today' --highlight-style=monochrome
HTML_META = -c manual.css

TITLE = -V title="MakeMeHappy Manual"

MAKEMYHAPPY_TEX_META = -V author="Frank Terbeck" $(TITLE)
MAKEMYHAPPY_HTML_META = $(MAKEMYHAPPY_TEX_META) --metadata title="mmh" --highlight-style=monochrome
MAKEMYHAPPY_MAN_META = -V title="mmh" -V section="1" -V date="Jan, 2021"

all: man html pdf info
man: $(MAN)
pdf: $(PDF)
html: $(HTML)
info: $(INFO)

mmh.1: mmh.mdwn
	pandoc -f markdown -t man $(CTOPS) $(MAKEMYHAPPY_MAN_META) -o $@ mmh.mdwn
mmh.pdf: mmh.mdwn
	pandoc -f markdown --template template.latex $(CTOPS) $(TEX_META) $(MAKEMYHAPPY_TEX_META) -o $@ mmh.mdwn
mmh.html: mmh.mdwn
	pandoc -f markdown -t html5 $(HTML_META) $(CTOPS) $(MAKEMYHAPPY_HTML_META) -o $@ mmh.mdwn
mmh.texi: mmh.mdwn
	pandoc -f markdown -t texinfo $(INFO_META) $(CTOPS) $(MAKEMYHAPPY_INFO_META) -o $@ mmh.mdwn
mmh.info: mmh.texi
	makeinfo --no-validate --force $< -o $@

clean:
	rm -f $(HTML) $(PDF) $(MAN) $(INFO) *.texi *~

.PHONY: all man html pdf clean
