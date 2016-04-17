from os import path
import sys

from docker.client import Client
from docker.utils import kwargs_from_env
from git import Repo, InvalidGitRepositoryError


class UserMessageException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def _get_repo(repo=None):
    if repo is None:
        try:
            repo = Repo('.')
        except InvalidGitRepositoryError:
            raise UserMessageException('To run this command you need to be in git source code directory.')
    return repo


def _get_current_branch(repo):
    return repo.git.rev_parse('--abbrev-ref', 'HEAD')


def _check_branch(repo):
    if _get_current_branch(repo) != 'master':
        raise UserMessageException('Please switch to master branch to release the docker image.')


def _check_docker_image_dir(docker_image_dir):
    dockerfile_path = path.join(docker_image_dir, 'Dockerfile')
    if not path.exists(dockerfile_path):
        raise UserMessageException('Unable to find Dockerfile at location %s' % dockerfile_path)

 def _init_docker():
     kwargs = kwargs_from_env()

     if 'tls' in kwargs:
         # see http://docker-py.readthedocs.org/en/latest/boot2docker/
         import requests.packages.urllib3 as urllib3

         urllib3.disable_warnings()
         kwargs['tls'].assert_hostname = False

     docker = Client(**kwargs)
     try:
         docker.version()
     except:
         raise UserMessageException("Please set up 'docker' correctly")
     return docker



def main():
    try:
        repo = _get_repo()
        _check_branch(repo)
        docker = _init_docker()
        for docker_image_dir in sys.argv:
            _check_docker_image_dir(docker_image_dir)

    except UserMessageException, e:
        print "ERROR: %s" % e
        return 1
