#!/usr/bin/make -f
# Makefile for HoustonPatchbay #
# ---------------------- #
# Created by houston4444
#

LRELEASE ?= lrelease
RCC ?= rcc
QT_VERSION ?= 6


# if you set QT_VERSION environment variable to 5 at the make command
# it will choose the other commands QT_API, pyuic5, pylupdate5.

ifeq ($(QT_VERSION), 6)
	QT_API ?= PyQt6
	PYUIC ?= pyuic6
	PYLUPDATE ?= pylupdate6

	ifeq (, $(which $(RCC)))
		RCC := /usr/lib/qt6/libexec/rcc
	endif

	ifeq (, $(shell which $(LRELEASE)))
		LRELEASE := lrelease-qt6
	endif
else
    QT_API ?= PyQt5
	PYUIC ?= pyuic5
	PYLUPDATE ?= pylupdate5
	RCC ?= rcc
	ifeq (, $(shell which $(LRELEASE)))
		LRELEASE := lrelease-qt5
	endif
endif

# neeeded for make install
BUILD_CFG_FILE := build_config
QT_API_INST := $(shell grep ^QT_API= $(BUILD_CFG_FILE) 2>/dev/null| cut -d'=' -f2)
QT_API_INST ?= PyQt5

# ---------------------

all: QT_PREPARE RES UI LOCALE

QT_PREPARE:
	$(info compiling for Qt$(QT_VERSION) using $(QT_API))
	$(file > $(BUILD_CFG_FILE),QT_API=$(QT_API))

    ifneq ($(QT_API), $(QT_API_INST))
		rm -f *~ source/patchbay/resources_rc.py \
			 locale/*.qm patchbay/ui/*.py
    endif
	install -d source/patchbay/ui/

# ---------------------
# Resources

RES: source/patchbay/resources_rc.py

source/patchbay/resources_rc.py: resources/resources.qrc
	${RCC} -g python $< |sed 's/ PySide. / qtpy /' > $@

# ---------------------
# UI code

UI: $(shell \
	ls resources/ui/*.ui| sed 's|\.ui$$|.py|'| sed 's|^resources/|source/patchbay/|')

source/patchbay/ui/%.py: resources/ui/%.ui
ifeq ($(PYUIC), pyuic6)
	$(PYUIC) $< > $@
	echo 'from .. import resources_rc' >> $@
else
	$(PYUIC) --import-from=.. $< > $@
endif
		
# ------------------------
# # Translations Files

LOCALE: locale/patchbay_en.qm  \
		locale/patchbay_fr.qm

locale/%.qm: locale/%.ts
	-$(LRELEASE) $< -qm $@

# -------------------------

clean:
	rm -f *~ source/patchbay/resources_rc.py \
			 locale/*.qm
	rm -f -R source/patchbay/ui \
			 source/patchbay/__pycache__ \
			 source/patchbay/*/__pycache__ \
			 source/patchbay/*/*/__pycache__

# -------------------------

debug:
	$(MAKE) DEBUG=true

# -------------------------
