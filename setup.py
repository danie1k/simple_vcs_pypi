import ast
import os
import re
from setuptools import setup

current_dir = os.path.abspath(os.path.dirname(__file__))
_version_re = re.compile(r'__version__\s+=\s+(?P<version>.*)')

with open(os.path.join(current_dir, 'gh_pypi', '__init__.py'), 'r') as f:
    version = _version_re.search(f.read()).group('version')
    version = str(ast.literal_eval(version))


setup(
    name='gh_pypi',
    license='MIT',
    version=version,
    description='GitHub-hosted Simple PyPi Index WSGI Application',
    long_description=open('README.rst').read(),
    author='Daniel Kuruc',
    author_email='daniel@kurur.dev',
    url='https://github.com/danie1k/github_hosted_pypi',
    py_modules=[
        'gh_pypi',
    ],
    zip_safe=False,
    python_requires='>3.0',
    install_requires=[
        'cachelib>=0.1,<0.2',
        'github3.py>=1.3.0,<1.4',
        'Werkzeug>=0.15.4,<0.16',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
