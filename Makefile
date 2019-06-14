lint:
	@pipenv run flake8 --config=./setup.cfg ./gh_pypi/
	@pipenv run pycodestyle --config=./setup.cfg ./gh_pypi/
	@pipenv run pylint --rcfile=./setup.cfg ./gh_pypi/

isort:
	@pipenv run isort -y -rc -sp=./setup.cfg ./gh_pypi/

yapf:
	@pipenv run yapf -i --recursive ./gh_pypi/

.PHONY: lint isort yapf
