PYTEST = pytest

.PHONY: test test-unit test-all version-update install-os-requirements install-os-requirements-arch install-requirements install-requirements-dev coverage-report
test:
	$(PYTEST) exchange/config/ -n 4 --maxfail=100 --dist=worksteal
	$(PYTEST) exchange/broker
	$(PYTEST) -m "not matcherFull" tests/ -n 4 --maxfail=100 --dist=worksteal
	$(PYTEST) exchange/blockchain/ -n 1
test-clean:
	$(PYTEST) exchange/config/ -n 4 --maxfail=100 --dist=worksteal
	$(PYTEST) exchange/broker
	$(PYTEST) -m "not matcherFull" tests/ -n 4 --maxfail=100 --dist=worksteal --create-db
	$(PYTEST) exchange/blockchain/ -n 1
test-ci:
	$(PYTEST) exchange/config/ -n 4 --maxfail=100 --dist=worksteal
	$(PYTEST) exchange/broker
	bash -o pipefail -c '$(PYTEST) -m "not matcherFull" tests/ -n 4 --maxfail=100 --dist=worksteal --create-db --junitxml=pytest.xml --cov-report=term-missing:skip-covered --cov=exchange | tee pytest-coverage.txt'
	$(PYTEST) exchange/blockchain/ -n 1
test-coverage:
	$(PYTEST) exchange/config/ -n 4 --maxfail=100 --dist=worksteal
	$(PYTEST) exchange/broker
	bash -o pipefail -c '$(PYTEST) -m "not matcherFull" tests/ -n 4 --maxfail=100 --dist=worksteal --junitxml=pytest.xml --cov-report=term-missing:skip-covered --cov=exchange | tee pytest-coverage.txt'
	$(PYTEST) exchange/blockchain/ -n 1
test-unit:
	$(PYTEST) -m "unit"
test-matcher:
	$(PYTEST) -m "matcher"
test-all:
	$(PYTEST) --runslow
version-update:
	sed -i -e "s/^CURRENT_COMMIT = '.*'$$/CURRENT_COMMIT = '$(shell git rev-parse --short HEAD)'/" exchange/settings.py
install-os-requirements:
	sudo apt install libsecp256k1-dev pkg-config
install-os-requirements-arch:
	sudo pacman -S libsecp256k1
install-requirements:
	pip install -q --upgrade -r requirements.txt
install-requirements-dev:
	pip install -q --upgrade -r requirements.txt -r requirements-dev.txt

install-requirements-m1: export GRPC_PYTHON_BUILD_SYSTEM_OPENSSL = 1
install-requirements-m1: export GRPC_PYTHON_BUILD_SYSTEM_ZLIB = 1
install-requirements-m1:
	pip install --upgrade -r requirements.txt

coverage-test:
	coverage run venv/bin/pytest
coverage-report:
	coverage html
	python3 -m http.server --bind 127.0.0.1 --directory htmlcov 8001
i18n-collect:
	python3 manage.py makemessages --locale=fa --ignore=venv/*
i18n-compile:
	python3 manage.py compilemessages --locale=fa

## Admin Code Sync ##
define admin_sync_migrations
	rsync -av --delete --delete-excluded --exclude=__pycache__ "exchange/$(1)/migrations/" "../admin/exchange/$(1)/migrations/"
endef

sync-with-admin:
	$(call admin_sync_migrations,accounting)
	$(call admin_sync_migrations,accounts)
	$(call admin_sync_migrations,base)
	$(call admin_sync_migrations,market)
	$(call admin_sync_migrations,promotions)
	$(call admin_sync_migrations,security)
	$(call admin_sync_migrations,shetab)
	$(call admin_sync_migrations,usermanagement)
	$(call admin_sync_migrations,wallet)

IMAGE_TAG=h-reg.nxbo.ir/core/core:$(shell git branch --show-current | sed 's/\//-/g')

build-image:
	docker build --ssh default -t $(IMAGE_TAG) . --target prod

push-image:
	docker push $(IMAGE_TAG)
