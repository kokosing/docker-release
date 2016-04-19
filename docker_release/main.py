from os import path
import sys
import json
import argparse

from docker.client import Client
from docker.utils import kwargs_from_env
from git import Repo, InvalidGitRepositoryError
import pkg_resources
import requests


class UserMessageException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)


def _get_repo(directory):
    directory = path.abspath(directory)
    while directory is not '/':
        try:
            return Repo(directory)
        except InvalidGitRepositoryError:
            directory = path.dirname(directory)
    raise UserMessageException('To run this command you need to be in git source code directory.')


def _get_current_branch(repo):
    return repo.git.rev_parse('--abbrev-ref', 'HEAD')


def _check_branch(repo):
    if _get_current_branch(repo) != 'master':
        raise UserMessageException('Please switch to master branch to release the docker image.')


def _get_docker_image_name(docker_image_dir):
    docker_file_path = path.join(docker_image_dir, 'Dockerfile')
    if not path.exists(docker_file_path):
        raise UserMessageException('Unable to find Dockerfile at location %s' % docker_file_path)

    return (path.basename(path.dirname(docker_image_dir)), path.basename(docker_image_dir))


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


def _get_tags(organization, repository):
    response = requests.get('https://registry.hub.docker.com/v1/repositories/%s/%s/tags' % (organization, repository))
    if response.status_code == 400:
        return []
    if response.status_code != 200:
        raise UserMessageException('Unable to get tags for: %s/%s' % (organization, repository))

    tags = {}
    for entry in response.json():
        tags[entry['name']] = entry['layer']
    return tags


def _get_next_version(tags):
    version = 1
    while version in tags:
        version += 1

    return version


def main():
    parser = argparse.ArgumentParser(description='Tool for releasing docker images.')
    parser.add_argument('--snapshot', '-s', action='store_true',
                        help="Release a snapshot version (push tags with git sha and updates 'latest')")
    parser.add_argument('docker_image_dir', metavar='dir', nargs='+',
                        help='Location of docker image directory with Dockerfile to be released')
    parser.add_argument('--version', action='version', version=pkg_resources.require("docker-release")[0].version)
    args = parser.parse_args(sys.argv[1:])
    print args
    try:
        for docker_image_dir in args.docker_image_dir:
            organization, repository = _get_docker_image_name(docker_image_dir)
            repo = _get_repo(docker_image_dir)
            if not args.snapshot:
                _check_branch(repo)
            tags = _get_tags(organization, repository)
            hash_tag = repo.head.commit.hexsha[:7]
            if hash_tag in tags:
                raise UserMessageException('This version is already released')
            docker = _init_docker()
            image = "%s/%s" % (organization, repository)
            print "building %s" % image
            for line in docker.build(docker_image_dir, image):
                print json.loads(line)['stream'][:-1]

            _docker_push(docker, image, hash_tag)
            if not args.snapshot:
                _docker_push(docker, image, _get_next_version(tags))
            _docker_push(docker, image, 'latest')

    except UserMessageException, e:
        print "ERROR: %s" % e
        return 1


def _docker_push(docker, image, tag):
    print "pushing %s:%s" % (image, tag)
    docker.push(image, tag)
