#
# GNU 'make' file
# 

# PY[23] is the target Python interpreter.  It must have pytest installed.
SHELL		= /bin/bash

PY		?= python
PY2		?= python2
PY2_V		= $(shell $(PY2) -c "import sys; print('-'.join((next(iter(filter(None,sys.executable.split('/')))),sys.platform,sys.subversion[0].lower(),''.join(map(str,sys.version_info[:2])))))"  )
PY3		?= python3
PY3_V		= $(shell $(PY3) -c "import sys; print('-'.join((next(iter(filter(None,sys.executable.split('/')))),sys.platform,sys.implementation.cache_tag)))" 2>/dev/null )

VERSION		= $(shell $(PY3) -c 'exec(open("version.py").read()); print( __version__ )')
WHEEL		= dist/cpppo_positioner-$(VERSION)-py3-none-any.whl

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

GHUB_NAME	= cpppo_positioner
GHUB_REPO	= git@github.com:pjkundert/$(GHUB_NAME).git
GHUB_BRCH	= $(shell git rev-parse --abbrev-ref HEAD )

# We'll agonizingly find the directory above this makefile's path
VENV_DIR	= $(abspath $(dir $(abspath $(lastword $(MAKEFILE_LIST))))/.. )
VENV_NAME	= $(GHUB_NAME)-$(VERSION)-$(PY3_V)
VENV		= $(VENV_DIR)/$(VENV_NAME)
VENV_OPTS	=

PY2TEST=TZ=$(TZ) $(PY2) -m pytest $(PYTESTOPTS)
PY3TEST=TZ=$(TZ) $(PY3) -m pytest $(PYTESTOPTS)

.PHONY: all test clean FORCE
all:			help

help:
	@echo "GNUmakefile for cpppo_positioner.  Targets:"
	@echo "  help			This help"
	@echo "  test			Run unit tests under Python2"
	@echo "  test-...		  Run only tests in ..._test.py"
	@echo "  unit-...		  Run only tests with names matching ..."
	@echo "  install		Install in /usr/local for Python2"
	@echo "  clean			Remove build artifacts"

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

build-check:
	@$(PY3) -m build --version \
	    || ( echo "\n*** Missing Python modules; run:\n\n        $(PY3) -m pip install --upgrade -r requirements-dev.txt\n" \
	        && false )

build:	build-check clean wheel

wheel:	$(WHEEL)

$(WHEEL):	FORCE
	$(PY3) -m pip install -r requirements-dev.txt
	$(PY3) -m build .
	@ls -last dist

install:	$(WHEEL) FORCE
	$(PY3) -m pip install --force-reinstall $<[all]

install-%:  # ...-dev, -tests
	$(PY3) -m pip install --upgrade -r requirements-$*.txt


#
# venv:		Create a Virtual Env containing the installed repo
#
.PHONY: venv
venv:			$(VENV)
	@echo; echo "*** Activating $< VirtualEnv for Interactive $(SHELL)"
	@bash --init-file $</bin/activate -i

$(VENV):
	@echo; echo "*** Building $@ VirtualEnv..."
	@rm -rf $@ && $(PY3) -m venv $(VENV_OPTS) $@ \
	    && source $@/bin/activate \
	    && make install install-tests



#
# nix-...:
#
# Use a NixOS environment to execute the make target, eg.
#
#     nix-venv-activate
#
#     The default is the Python 3 crypto_licensing target in default.nix; choose
# TARGET=py27 to test under Python 2 (more difficult as time goes on).  See default.nix for
# other Python version targets.
#
nix-%:
	nix-shell $(NIX_OPTS) --run "make $*"


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
