# Nobitex Core
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Nobitex Core handles main functionality of Nobitex exchange, including providing the exchange API, order management and matching engine, implementing blockchain systems interface, and many other features of Nobitex.

# Development Guide
## Requirements
* Python Version: Currently core code must be runnable on Python 3.8, but minimum required Python version is planned to be upgraded to 3.11 (See issue #45).
* Datastore: PostgreSQL and Redis must be installed locally.
* Packages: cmake build-essential libffi-dev libpq-dev python3-virtualenv python3-dev python3-setuptools python3-pip python3-smbus python3-openssl libsecp256k1-dev pkg-config zlib1g zlib1g-dev software-properties-common

## Running Project
* Create a virtualenv and install requirements specified in `requirements.txt` and `requirements-dev.txt`. Always install requirements with `--upgrade` and try not to pin any package version unless there is reason to use a specific version.
* Initialize and update submodules: `git submodule init` and `git submodule update`. Learn more in [Pro Git book](https://git-scm.com/book/en/v2/Git-Tools-Submodules).
* Configure PostgreSQL: Create a database named `nobitex` and a user named `your system username` with full access to it.
```commandline
 $ sudo -i -u postgres
 $ createuser --interactive
 $ createdb nobitex

```
* Run migrations: `./manage.py migrate`.
* Load initial data: `./manage.py loaddata system`.
* Install pre-commit Git hooks: `pre-commit install && pre-commit install --hook-type commit-msg -f`.
* Run tests: `make test`.
* Start the development server and happy developing!

## Debug Email Templates in Local Machine
* Update email templates in database: `POST_OFFICE_CACHE=False python manage.py update_email_templates`.
* Generate html output of email in `debug_templates` folder: `python manage.py local_email_template_generator --template <template name> --data '{"key": "value"}'`.


## Troubleshooting
* Problem in running tests: Make sure you are using `pytest` to run tests. Also create a database named `test_nobitex` and grant full access on it to `nobitex` user.


## Build Docker Image

* This command will build an image for the current branch, with the name of the branch as tag.

```commandline
$ make build-image
```

## Push Image to Registry

```commandline
$ make push-image
```
