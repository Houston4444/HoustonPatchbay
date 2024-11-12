#!/usr/bin/make -f
# Makefile for HoustonPatchbay #
# ---------------------- #
# Created by houston4444
#

LRELEASE ?= lrelease
QT_VERSION ?= 5
PYRCC := pyrcc5


# if you set QT_VERSION environment variable to 6 at the make command
# it will choose the other commands QT_API, pyuic6, pylupdate6.

ifeq ($(QT_VERSION), 6)
	QT_API ?= PyQt6
	PYUIC ?= pyuic6
	PYLUPDATE ?= pylupdate6
	ifeq (, $(shell which $(LRELEASE)))
		LRELEASE := lrelease-qt6
	endif
else
    QT_API ?= PyQt5
	PYUIC ?= pyuic5
	PYLUPDATE ?= pylupdate5
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

    ifeq ($(QT_API), $(QT_API_INST))
    else
		rm -f *~ patchbay/resources_rc.py \
			 locale/*.qm patchbay/ui/*.py
    endif
	install -d patchbay/ui/

# ---------------------
# Resources

RES: patchbay/resources_rc.py

patchbay/resources_rc.py: resources/resources.qrc
	rcc -g python $< |sed 's/ PySide. / qtpy /' > $@

# ---------------------
# UI code

UI: $(shell \
	ls resources/ui/*.ui| sed 's|\.ui$$|.py|'| sed 's|^resources/|patchbay/|')

patchbay/ui/%.py: resources/ui/%.ui
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
	$(LRELEASE) $< -qm $@

locale/%.qm: locale/%.ts
	$(LRELEASE) $< -qm $@

# -------------------------

clean:
	rm -f *~ patchbay/resources_rc.py \
			 locale/*.qm
	rm -f -R patchbay/ui \
			 patchbay/__pycache__ \
			 patchbay/*/__pycache__ \
			 patchbay/*/*/__pycache__

# -------------------------

debug:
	$(MAKE) DEBUG=true

# -------------------------
