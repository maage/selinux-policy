# SPDX-FileCopyrightText: 2021 Markus Linnala <markus.linnala@cybercom.com>
#
# SPDX-License-Identifier: Apache-2.0

MLSENABLED ?=
QUIET := n
verbose ?=

SELINT ?= selint
SEMOD_LNK ?= semodule_link # -v
SEMOD_EXP ?= semodule_expand
SEPOLGEN ?= sepolgen-ifgen -v
SUDO ?= sudo
base_pkg = base.pp

.PHONY: all check default lint validate

default: all
	$(SUDO) $(MAKE) load

#

include /usr/share/selinux/devel/Makefile

SEMODULE = $(SBINDIR)/semodule -v

# lint
SELINT_ARGS_fc = --disable=E-005
SELINT_ARGS_te = --disable=S-001
SELINT_ARGS_if =
define selint_template
tmp/lint.$(1).flag: $$(all_packages:.pp=.$(1))
	$(SELINT) $$(SELINT_ARGS_$(1)) $$?
	@touch -- $$@
lint: tmp/lint.$(1).flag
endef
$(foreach suf,fc if te,$(eval $(call selint_template,$(suf))))

check: lint

# validate
$(base_pkg):
	$(verbose) $(SUDO) $(SEMODULE) --hll --extract=$(@:.pp=)
tmp/validate.lnk: $(base_pkg) $(all_packages)
	$(verbose) $(SEMOD_LNK) -o $@ $^
tmp/validate.policy.bin: tmp/validate.lnk
	$(verbose) $(SEMOD_EXP) $^ $@
tmp/validate.output: tmp/validate.policy.bin
	$(verbose) $(SEPOLGEN) --policy=$^ --interfaces=$(HEADERDIR) --output=$@
validate: tmp/validate.output

check: validate
