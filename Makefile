# PiaPort build / deploy helpers.
#
# The egg must be built against the SAME Python the Deluge container ships, so we
# build inside the container's own image (auto-detected) rather than assuming a
# version. Override any variable on the command line, e.g.:
#   make install DELUGE_CONTAINER=deluge

DELUGE_CONTAINER ?= deluge
PLUGIN           := PiaPort
IMAGE            = $(shell docker inspect -f '{{.Config.Image}}' $(DELUGE_CONTAINER))
# Path to the Deluge-bundled Python inside the container (LSIO image default).
PYTHON           ?= /lsiopy/bin/python3

.PHONY: help test egg install enable status clean

help:
	@echo "Targets:"
	@echo "  test     - run the unit tests (host pytest)"
	@echo "  egg      - build the plugin egg in the Deluge container's image"
	@echo "  install  - build, copy the egg into the container, restart it"
	@echo "  enable   - enable the plugin in the running daemon"
	@echo "  status   - print the plugin's live status over the daemon RPC"
	@echo "  clean    - remove build artifacts"

test:
	python3 -m pytest -q

egg: clean
	docker run --rm --entrypoint python3 --user "$(shell id -u):$(shell id -g)" -e HOME=/tmp \
	  -v "$(CURDIR)":/src -w /src "$(IMAGE)" setup.py bdist_egg -d /src/dist
	@echo "Built:" && ls -1 dist/$(PLUGIN)-*.egg

# Replace any previously installed egg so Deluge can't load a stale version.
install: egg
	docker exec $(DELUGE_CONTAINER) sh -c 'rm -f /config/plugins/$(PLUGIN)-*.egg'
	docker cp dist/$(PLUGIN)-*.egg $(DELUGE_CONTAINER):/config/plugins/
	docker restart $(DELUGE_CONTAINER)
	@echo "Installed. Wait a few seconds, then: make enable"

# Waits for the daemon RPC to come up (install restarts the container) and
# confirms the plugin actually shows as enabled before reporting success.
enable:
	@echo "Enabling $(PLUGIN) (waiting for the Deluge daemon)..."; \
	for i in $$(seq 1 30); do \
	  PW=$$(docker exec $(DELUGE_CONTAINER) sh -c "awk -F: '/^localclient:/{print \$$2}' /config/auth" 2>/dev/null); \
	  if [ -n "$$PW" ]; then \
	    docker exec $(DELUGE_CONTAINER) deluge-console -U localclient -P "$$PW" "plugin -e $(PLUGIN)" >/dev/null 2>&1; \
	    if docker exec $(DELUGE_CONTAINER) deluge-console -U localclient -P "$$PW" "plugin -s" 2>/dev/null \
	        | awk '/^Enabled Plugins:/{e=1;next} /^[^[:space:]]/{e=0} e && $$1=="$(PLUGIN)"{f=1} END{exit f?0:1}'; then \
	      echo "Enabled $(PLUGIN). Configure it in the web UI: Preferences > $(PLUGIN)"; \
	      exit 0; \
	    fi; \
	  fi; \
	  sleep 1; \
	done; \
	echo "Timed out waiting for the Deluge daemon to enable $(PLUGIN)" >&2; \
	exit 1

status:
	docker cp scripts/piaport-status.py $(DELUGE_CONTAINER):/tmp/piaport-status.py
	docker exec $(DELUGE_CONTAINER) $(PYTHON) /tmp/piaport-status.py

clean:
	rm -rf build dist *.egg-info $(PLUGIN).egg-info deluge_piaport.egg-info
