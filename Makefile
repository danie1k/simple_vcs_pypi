lint:
	@pipenv run flake8 --config=./setup.cfg ./simple_vcs_pypi/
	@pipenv run pycodestyle --config=./setup.cfg ./simple_vcs_pypi/
	@pipenv run pylint --rcfile=./setup.cfg ./simple_vcs_pypi/

isort:
	@pipenv run isort -y -rc -sp=./setup.cfg ./simple_vcs_pypi/

yapf:
	@pipenv run yapf -i --recursive ./simple_vcs_pypi/

.PHONY: lint isort yapf
