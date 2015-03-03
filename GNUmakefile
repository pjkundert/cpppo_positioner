#
# GNU 'make' file
# 

# PY[23] is the target Python interpreter.  It must have pytest installed.

PY2=python
PY3=python3

# PY[23]TEST is the desired method of invoking py.test; either as a command, or
# loading it as module, by directly invoking the target Python interpreter.
# 
# Ensure your locale is set to a UTF-8 encoding; run 'locale'; you should see something like:
 
#     LANG=en_CA.UTF-8
#     LANGUAGE=en_CA:en
#     LC_CTYPE="en_CA.UTF-8"
#     LC_NUMERIC="en_CA.UTF-8"
#     LC_TIME="en_CA.UTF-8"
#     LC_COLLATE="en_CA.UTF-8"
#     LC_MONETARY="en_CA.UTF-8"
#     LC_MESSAGES="en_CA.UTF-8"
#     LC_PAPER="en_CA.UTF-8"
#     LC_NAME="en_CA.UTF-8"
#     LC_ADDRESS="en_CA.UTF-8"
#     LC_TELEPHONE="en_CA.UTF-8"
#     LC_MEASUREMENT="en_CA.UTF-8"
#     LC_IDENTIFICATION="en_CA.UTF-8"
#     LC_ALL=en_CA.UTF-8
#     ...
# 
# Set in your .bashrc:
#     LANG=en_CA.UTF-8
#     LC_ALL=en_CA.UTF-8
# 

# To see all pytest output, uncomment --capture=no
PYTESTOPTS=-v # --capture=no

# Preferred timezone for tests.  If you change this, then you will probably have
# to augment history_test.py to include checking for timestamp.local output in
# your local timezone; See history_test.py test_history_timestamp() for supported
# zones
TZ=Canada/Mountain

PY2TEST=TZ=$(TZ) $(PY2) -m pytest $(PYTESTOPTS)
PY3TEST=TZ=$(TZ) $(PY3) -m pytest $(PYTESTOPTS)

.PHONY: all test clean upload
all:			help

help:
	@echo "GNUmakefile for cpppo.  Targets:"
	@echo "  help			This help"
	@echo "  test			Run unit tests under Python2"
	@echo "  test-...		  Run only tests in ..._test.py"
	@echo "  unit-...		  Run only tests with names matching ..."
	@echo "  install		Install in /usr/local for Python2"
	@echo "  clean			Remove build artifacts"
	@echo "  upload			Upload new version to pypi (package maintainer only)"

test:
	$(PY2TEST) || true
#	$(PY3TEST) || true

install:
	$(PY2) setup.py install
#	$(PY3) setup.py install

# Support uploading a new version of cpppo to pypi.  Must:
#   o advance __version__ number in cpppo/misc.py
#   o log in to your pypi account (ie. for package maintainer only)
upload:
	python setup.py sdist upload

clean:
	rm -f MANIFEST *.png $(shell find . -name '*.pyc' )
	rm -rf build dist auto __pycache__ *.egg-info

analyze:
	flake8 -j 1 --max-line-length=110                                       \
	  --ignore=E221,E201,E202,E203,E223,E225,E226,E231,E241,E242,E261,E272,E302,W503,E701,E702,E,W  \
	  --exclude="__init__.py" \
	  .

# Run only tests with a prefix containing the target string, eg test-blah
test-%:
	$(PY2TEST) *$*_test.py
#	$(PY3TEST) *$*_test.py

unit-%:
	$(PY2TEST) -k $*
#	$(PY3TEST) -k $*


#
# Target to allow the printing of 'make' variables, eg:
#
#     make print-CXXFLAGS
#
print-%:
	@echo $* = $($*)
	@echo $*\'s origin is $(origin $*)
