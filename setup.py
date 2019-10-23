from setuptools import setup, find_packages

requirements = [
    'GitPython == 1.0.1',
    'docker-py >= 1.7.0',
    'requests ==2.20.0'
]

setup_requirements = [
    'flake8'
]

description = """
Tool for releasing docker images. It is useful when your docker image files
are under continuous development and you want to have a
convenient way to release (publish) them.

This utility supports:

 - tagging git repository when a docker image gets released
 - tagging docker image with a git hash commit
 - incrementing docker image version (tag)
 - updating 'latest' tag in the docker hub
"""

setup(
    name='docker-release',
    version='0.9-SNAPSHOT',
    description=description,
    author='Grzegorz Kokosinski',
    author_email='g.kokosinski a) gmail.com',
    keywords='docker image release',
    url='https://github.com/kokosing/docker-release',
    packages=find_packages(),
    package_dir={'docker_release': 'docker_release'},
    install_requires=requirements,
    setup_requires=setup_requirements,
    entry_points={'console_scripts': ['docker-release = docker_release.main:main']}
)
