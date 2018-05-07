#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.rst') as readme_file:
    readme = readme_file.read()

with open('HISTORY.rst') as history_file:
    history = history_file.read()

requirements = [ ]

setup_requirements = [ ]

test_requirements = [ ]

setup(
    author="Davide Rizzo",
    author_email='sorcio@gmail.com',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Python Software Foundation License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],
    description="AsyncExitStack backport for Python 3.5+",
    install_requires=requirements,
    license="Python Software Foundation License",
    long_description=readme + '\n\n' + history,
    include_package_data=True,
    keywords='async_exit_stack',
    name='async_exit_stack',
    packages=find_packages(include=['async_exit_stack']),
    python_requires='>=3.5',
    setup_requires=setup_requirements,
    test_suite='tests',
    tests_require=test_requirements,
    url='https://github.com/sorcio/async_exit_stack',
    version='1.0.1',
    zip_safe=False,
)
