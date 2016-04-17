from setuptools import setup, find_packages

requirements = [
    'GitPython==1.0.1',
    'docker-py >= 1.7.0'
]

setup_requirements = [
    'flake8'
]

setup(
    name='docker-release',
    version='0.1-SNAPSHOT',
    description='Tool for releasing docker images.',
    author='Grzegorz Kokosinski',
    author_email='g.kokosinski a) gmail.com',
    keywords='docker image release',
    url='https://github.com/kokosing/docker_release',
    packages=find_packages(exclude=['*tests*']),
    package_dir={'docker_release': 'docker_release'},
    install_requires=requirements,
    setup_requires=setup_requirements,
    entry_points={'console_scripts': ['docker-release = docker_release.main:main']}
)
