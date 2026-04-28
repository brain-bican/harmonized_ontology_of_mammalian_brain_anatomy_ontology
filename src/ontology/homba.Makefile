## Customize Makefile settings for homba
## 
## If you need to customize your Makefile, make
## changes here rather than in the main Makefile

URIBASE = https://purl.brain-bican.org/ontology

# Update this single URL when switching HOMBA structure graph versions.
HOMBA_DOWNLOAD_URL ?= https://alleninstitute.github.io/CCF-MAP/_downloads/4ebd4f47528d60cd67ecb4571019bf69/HOMBA_v1.1.0.json
HOMBA_JSON = $(TMPDIR)/HOMBA.json

JOBS = HOMBA
BRIDGES = homba
TARGETS = homba

LINKML = linkml-data2owl

STRUCTURE_GRAPHS = $(HOMBA_JSON)
HOMBA_TEMPLATE = ../linkml/data/HOMBA.tsv
ALL_GRAPH_ONTOLOGIES = sources/HOMBA.ofn
ALL_BRIDGES = $(patsubst %, sources/uberon-bridge-to-%.owl, $(BRIDGES))
# Keep the template-regenerated bridge workflow disabled until HOMBA has a
# manually curated mapping table to compare against the legacy bridge.
# SOURCE_TEMPLATES = $(patsubst %, ../templates/%_CCF_to_UBERON_source.tsv, $(TARGETS))
# NEW_BRIDGES = $(patsubst %, new-bridges/new-uberon-bridge-to-%.owl, $(TARGETS))


.PHONY: $(COMPONENTSDIR)/all_templates.owl
$(COMPONENTSDIR)/all_templates.owl: clean_files dependencies $(COMPONENTSDIR)/linkouts.owl $(COMPONENTSDIR)/sources_merged.owl
	$(ROBOT) merge -i $(COMPONENTSDIR)/linkouts.owl -i $(COMPONENTSDIR)/sources_merged.owl annotate --ontology-iri $(URIBASE)/$@ convert -f ofn -o $@
.PRECIOUS: $(COMPONENTSDIR)/all_templates.owl

.PHONY: dependencies
dependencies:
	python3 -m pip install --break-system-packages -r ../../requirements.txt


LOCAL_CLEAN_FILES = $(HOMBA_JSON) $(ALL_GRAPH_ONTOLOGIES) $(ALL_BRIDGES) $(TMPDIR)/tmp.json $(TMPDIR)/tmp.owl $(COMPONENTSDIR)/sources_merged.owl $(COMPONENTSDIR)/linkouts.owl $(TEMPLATEDIR)/linkouts.tsv
# Template-regenerated bridge artifacts to restore later if HOMBA gets a curated mapping workflow:
# LOCAL_CLEAN_FILES += $(SOURCE_TEMPLATES) $(NEW_BRIDGES)

.PHONY: clean_files
clean_files:
	rm -f $(LOCAL_CLEAN_FILES)

$(HOMBA_JSON):
	mkdir -p $(dir $@)
	curl -L -o $@ "$(HOMBA_DOWNLOAD_URL)"

$(HOMBA_TEMPLATE): $(HOMBA_JSON)
	mkdir -p $(dir $@)
	python3 $(SCRIPTSDIR)/structure_graph_template.py -i $< -o $@
.PRECIOUS: $(HOMBA_TEMPLATE)

sources/HOMBA.ofn: $(HOMBA_TEMPLATE)
	mkdir -p $(dir $@)
	$(LINKML) -C Class -s ../linkml/structure_graph_schema.yaml $< -o $@
.PRECIOUS: sources/HOMBA.ofn

sources/uberon-bridge-to-homba.owl:
	mkdir -p $(dir $@)
	curl -L -o $(TMPDIR)/uberon-bridge-to-homba.download.owl "https://raw.githubusercontent.com/obophenotype/uberon/refs/heads/add-homba-bridge/src/ontology/bridge/uberon-bridge-to-homba.owl"
	python3 $(SCRIPTSDIR)/normalize_homba_bridge_xml.py $(TMPDIR)/uberon-bridge-to-homba.download.owl $@

# Disabled for now: provenance/template regeneration workflow that compares the legacy bridge
# against a manually curated HOMBA mapping table and rebuilds a fresh bridge.
# $(TMPDIR)/%_old_mapping.tsv: sources/uberon-bridge-to-%.owl
# 	$(ROBOT) query --input $< --query ../sparql/bridge_mappings.sparql $@
#
# ../templates/%_CCF_to_UBERON_source.tsv: $(TMPDIR)/%_old_mapping.tsv ../templates/%_CCF_to_UBERON.tsv
# 	python3 ../scripts/mapping_source_template_generator.py -i1 $< -i2 $(word 2, $^) -o $@
# .PRECIOUS: ../templates/%_CCF_to_UBERON_source.tsv
#
# new-bridges/new-uberon-bridge-to-%.owl: ../templates/%_CCF_to_UBERON.tsv ../templates/%_CCF_to_UBERON_source.tsv $(MIRRORDIR)/uberon.owl
# 	mkdir -p $(dir $@)
# 	$(ROBOT) template --input $(MIRRORDIR)/uberon.owl --template $< --output $(TMPDIR)/sourceless-new-uberon-bridge.owl
# 	$(ROBOT) template --input $(MIRRORDIR)/uberon.owl --template $(word 2, $^) --output $(TMPDIR)/CCF_to_UBERON_source.owl
# 	$(ROBOT) merge --input $(TMPDIR)/sourceless-new-uberon-bridge.owl --output $(TMPDIR)/CCF_to_UBERON_source.owl --output $@

$(COMPONENTSDIR)/sources_merged.owl: $(ALL_GRAPH_ONTOLOGIES) $(ALL_BRIDGES)
	$(ROBOT) merge $(patsubst %, -i %, $^) relax annotate --ontology-iri $(URIBASE)/$@ -o $@

$(TMPDIR)/tmp.owl: $(SRC) $(COMPONENTSDIR)/sources_merged.owl
	$(ROBOT) merge $(patsubst %, -i %, $^) relax annotate --ontology-iri $(URIBASE)/$@ -o $@

$(TMPDIR)/tmp.json: $(TMPDIR)/tmp.owl
	$(ROBOT) convert --input $< -f json -o $@

$(TEMPLATEDIR)/linkouts.tsv: $(TMPDIR)/tmp.json
	python3 $(SCRIPTSDIR)/gen_linkout_template.py $<
	python3 $(SCRIPTSDIR)/validate_linkout_template.py $(TEMPLATEDIR)/linkouts.tsv

$(COMPONENTSDIR)/linkouts.owl: $(TMPDIR)/tmp.owl $(TEMPLATEDIR)/linkouts.tsv
	$(ROBOT) template --template $(word 2, $^) --input $< --add-prefixes template_prefixes.json -o $@


## ONTOLOGY: uberon (remove disjoint classes and properties to keep merged bridge reasoning tractable)
.PHONY: mirror-uberon
.PRECIOUS: $(MIRRORDIR)/uberon.owl
mirror-uberon: | $(TMPDIR)
	if [ $(MIR) = true ] && [ $(IMP) = true ]; then $(ROBOT) convert -I http://purl.obolibrary.org/obo/uberon/uberon-base.owl -o $(TMPDIR)/uberon-download.owl && \
		$(ROBOT) remove -i $(TMPDIR)/uberon-download.owl --axioms disjoint -o $(TMPDIR)/$@.owl; fi


## Disable '--equivalent-classes-allowed asserted-only' due to bridge-level equivalence patterns
.PHONY: reason_test
reason_test: $(EDIT_PREPROCESSED) $(OTHER_SRC) $(IMPORT_FILES)
	$(ROBOT) reason --input $< --reasoner ELK \
		--exclude-tautologies structural --output test.owl && rm test.owl

BFO_SUPERCLASS_FILTER = query --update ../sparql/remove-bfo-inferred-superclasses.ru

## Disable '--equivalent-classes-allowed asserted-only' for the base release
## because HOMBA currently contains inferred equivalent classes.
$(ONT)-base.owl: $(EDIT_PREPROCESSED) $(OTHER_SRC) $(IMPORT_FILES)
	$(ROBOT_RELEASE_IMPORT_MODE) \
	reason --reasoner $(REASONER) --exclude-tautologies structural --annotate-inferred-axioms false \
	relax $(RELAX_OPTIONS) \
	reduce -r $(REASONER) $(REDUCE_OPTIONS) \
	remove --base-iri $(URIBASE)/HOMBA --axioms external --preserve-structure false --trim false \
	$(BFO_SUPERCLASS_FILTER) \
	$(SHARED_ROBOT_COMMANDS) \
	annotate --link-annotation http://purl.org/dc/elements/1.1/type http://purl.obolibrary.org/obo/IAO_8000001 \
		--ontology-iri $(ONTBASE)/$@ $(ANNOTATE_ONTOLOGY_VERSION) \
		--output $@.tmp.owl && mv $@.tmp.owl $@

$(ONT)-full.owl: $(EDIT_PREPROCESSED) $(OTHER_SRC) $(IMPORT_FILES)
	$(ROBOT_RELEASE_IMPORT_MODE) \
		reason --reasoner ELK --exclude-tautologies structural \
		relax \
		reduce -r ELK \
		$(BFO_SUPERCLASS_FILTER) \
		$(SHARED_ROBOT_COMMANDS) annotate --ontology-iri $(ONTBASE)/$@ $(ANNOTATE_ONTOLOGY_VERSION) --output $@.tmp.owl && mv $@.tmp.owl $@

$(ONT)-simple.owl: $(EDIT_PREPROCESSED) $(OTHER_SRC) $(SIMPLESEED) $(IMPORT_FILES)
	$(ROBOT_RELEASE_IMPORT_MODE) \
		reason --reasoner ELK --exclude-tautologies structural \
		relax \
		remove --axioms equivalent \
		relax \
		filter --term-file $(SIMPLESEED) --select "annotations ontology anonymous self" --trim true --signature true \
		reduce -r ELK \
		$(BFO_SUPERCLASS_FILTER) \
		query --update ../sparql/inject-subset-declaration.ru --update ../sparql/inject-synonymtype-declaration.ru \
		$(SHARED_ROBOT_COMMANDS) annotate --ontology-iri $(ONTBASE)/$@ $(ANNOTATE_ONTOLOGY_VERSION) --output $@.tmp.owl && mv $@.tmp.owl $@

$(ONT)-simple-non-classified.owl: $(EDIT_PREPROCESSED) $(OTHER_SRC) $(SIMPLESEED) $(IMPORT_FILES)
	$(ROBOT_RELEASE_IMPORT_MODE_BASE) \
		remove --axioms equivalent \
		reduce -r $(REASONER) $(REDUCE_OPTIONS) \
		filter --select ontology --term-file $(SIMPLESEED) --trim false \
		$(BFO_SUPERCLASS_FILTER) \
		$(SHARED_ROBOT_COMMANDS) annotate --ontology-iri $(ONTBASE)/$@ $(ANNOTATE_ONTOLOGY_VERSION) --output $@.tmp.owl && mv $@.tmp.owl $@

$(ONT).owl: $(ONT)-full.owl
	$(ROBOT) annotate --input $< --ontology-iri $(ONTBASE)/$@ $(ANNOTATE_ONTOLOGY_VERSION) \
		convert -o $@.tmp.owl && mv $@.tmp.owl $@

$(ONT).json: $(ONT).owl
	$(ROBOT) annotate --input $< --ontology-iri $(ONTBASE)/$@ $(ANNOTATE_ONTOLOGY_VERSION) \
		convert --check false -f json -o $@.tmp.json && \
		mv $@.tmp.json $@
