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


def _get_repo(directory):
    directory = path.abspath(directory)
    while directory is not '/':
        try:
            repo = Repo(directory)
            if repo.is_dirty():
                raise UserMessageException('Please commit or stash all the changes')
            return repo
        except InvalidGitRepositoryError:
            directory = path.dirname(directory)
    raise UserMessageException('To run this command you need to be in git source code directory.')


def _get_current_branch(repo):
    return repo.git.rev_parse('--abbrev-ref', 'HEAD')


def _check_branch(repo):
    if _get_current_branch(repo) != 'master':
        raise UserMessageException('Please switch to master branch to release the docker image.')


def _get_docker_image_name(docker_image_dir):
    docker_image_dir = path.abspath(docker_image_dir)
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
    print response
    if response.status_code == 404:
        return []
    if response.status_code != 200:
        raise UserMessageException('Unable to get tags for: %s/%s' % (organization, repository))

    tags = {}
    for entry in response.json():
        tags[entry['name']] = entry['layer']
    return tags


def _get_next_version(tags):
    max = 0
    for tag in tags:
        try:
            tag = float(tag)
            if tag > max:
                max = tag
        except ValueError:
            pass

    return int(max + 1)


def _docker_build(docker, args, docker_image_dir, image):
    print "Building %s" % image
    for line in docker.build(docker_image_dir, image):
        line = json.loads(line)
        if 'error' in line:
            raise UserMessageException('While building image: %s: %s' % (image, line['error']))
        elif args.verbose and 'stream' in line:
            print line['stream'][:-1]
        elif args.verbose and 'status' in line:
            print line['status'][:-1]
        elif args.verbose:
            print line


def _docker_push(docker, args, image, tag):
    image_without_tag = image[:image.find(':')]
    print "tagging %s:%s" % (image_without_tag, tag)
    images = docker.images(image)
    if len(images) != 1:
        raise UserMessageException('Expected only one image for: %s' % image)
    docker.tag(images[0]['Id'], image_without_tag, tag)
    if args.build:
        return
    print "pushing %s:%s to docker hub" % (image_without_tag, tag)
    for line in docker.push(image, tag, stream=True):
        line = json.loads(line)
        if 'error' in line:
            raise UserMessageException('While pushing image: %s: %s' % (image, line['error']))
        elif args.verbose and 'id' in line:
            print '%s: %s' % (line['id'], line['status'])
        elif args.verbose and 'status' in line:
            print line['status']
        elif args.verbose:
            print line


def main():
    parser = argparse.ArgumentParser(description='Tool for releasing docker images.')
    parser.add_argument('--snapshot', '-s', action='store_true',
                        help="Release a snapshot version (push tags with git sha and updates 'latest').")
    parser.add_argument('--force', '-f', action='store_true',
                        help='Release even if it is already released.')
    parser.add_argument('--build', '-b', action='store_true',
                        help='Just build and tag locally. Do not push to docker hub.')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Accept suggested answers for all the questions. Noninteractive mode.')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Make ouput more verbose (print output from docker daemon).')
    parser.add_argument('docker_image_dir', metavar='dir', nargs='+',
                        help='Location of docker image directory with Dockerfile to be released')
    parser.add_argument('--version', action='version', version=pkg_resources.require("docker-release")[0].version)
    args = parser.parse_args(sys.argv[1:])
    try:
        for docker_image_dir in args.docker_image_dir:
            organization, repository = _get_docker_image_name(docker_image_dir)
            repo = _get_repo(docker_image_dir)
            if not args.snapshot:
                _check_branch(repo)
            tags = _get_tags(organization, repository)
            hash_tag = repo.head.commit.hexsha[:7]
            if not args.force and hash_tag in tags:
                raise UserMessageException('This version is already released to docker hub')
            docker = _init_docker()
            image = '%s/%s:latest' % (organization, repository)
            _docker_build(docker, args, docker_image_dir, image)

            if not args.snapshot:
                version = _get_next_version(tags)
                if not args.yes:
                    user_version = raw_input('What version number would you like to release (%s): ' % version)
                    if user_version is not '':
                        version = user_version
                git_tag = '%s/%s/%s' % (organization, repository, version)
                if git_tag in repo.tags:
                    raise UserMessageException('This version is already released, contains a tag in git: %s' % git_tag)
                _docker_push(docker, args, image, version)
                repo.git.tag(git_tag)
                repo.git.push('--tags')
            _docker_push(docker, args, image, hash_tag)
            _docker_push(docker, args, image, 'latest')

    except UserMessageException, e:
        print "ERROR: %s" % e.value
        return 1
