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
        answer = raw_input('You are going to release from non master branch, is that intentional? [N/y]: ')
        if answer is not 'y' or answer is not 'Y':
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
    #
    # Documentation eludes us, but this seems to return the complete list of
    # tags.
    #
    # v1 of the Registry API is documented to return all of the tags for a
    # repository:
    # https://docs.docker.com/v1.7/reference/api/hub_registry_spec/#tags-registry
    #
    # The observed behavior is that it does not:
    # https://registry.hub.docker.com/v1/repositories/teradatalabs/cdh5-hive/tags
    # returns a subset of the tags that are shown here:
    # https://hub.docker.com/r/teradatalabs/cdh5-hive/tags/
    #
    # Note that the observed behavior here doesn't appear to conform to the
    # documented behavior for the v2 Registry API in even the slightest
    # respect:
    # https://docs.docker.com/registry/spec/api/#/listing-image-tags
    #
    response = requests.get('https://registry.hub.docker.com/v2/repositories/%s/%s/tags/' % (organization, repository))
    if response.status_code == 404:
        return []
    if response.status_code != 200:
        raise UserMessageException('Unable to get tags for: %s/%s' % (organization, repository))

    tags = []
    for tag in response.json()['results']:
        tags.append(tag['name'])
    return tags


def _get_next_version(tags):
    max = 0
    for tag in tags:
        try:
            # Don't treat tags that are short git hashes that happen to be 7
            # decimal digits as versions.
            if len(tag) == 7:
                continue

            tag = float(tag)

            if tag > max:
                max = tag
        except ValueError:
            pass

    return int(max + 1)


def _docker_build(docker, args, docker_image_dir, image):
    if args.no_build:
        print "Skipping build for %s" % image
        return
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
    if args.dry_run:
        print "Skipping push for %s" % image
        return
    print "pushing %s:%s to docker hub" % (image_without_tag, tag)
    for multiline in docker.push(image, tag, stream=True):
        """
        docker push is documented[0] to return a JSON formatted string with one
        object per line. Sometimes the generator returns multiple lines in one
        string. Split the string on newlines so that we're feeding the JSON
        parser one line at a time. Failing to do so results in JSON parsing
        errors when the parser reaches the start of the next object.

        [0] http://docker-py.readthedocs.io/en/latest/api/#push
        """
        for line in multiline.split('\n'):
            # Skip blank lines, which also trip up the JSON parser.
            if not line.strip():
                continue

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
    parser.add_argument('--force', '-f', action='store_true',
                        help='Release even if it is already released.')
    parser.add_argument('--dry-run', '-d', action='store_true',
                        help='Just build and tag locally. Do not push to docker hub.')
    parser.add_argument('--no-build', '-B', action='store_true',
                        help='Do not build images. Tag and push current :latest')
    parser.add_argument('--tag-once', '-T', action='store_true',
                        help='Tag the git repository once with release-<version> rather than per-image')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Accept suggested answers for all the questions. Noninteractive mode.')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Make ouput more verbose (print output from docker daemon).')
    parser.add_argument('docker_image_dir', metavar='dir', nargs='+',
                        help='Location of docker image directory with Dockerfile to be released')
    parser.add_argument('--version', action='version', version=pkg_resources.require("docker-release")[0].version)

    type_group = parser.add_mutually_exclusive_group()
    type_group.add_argument('--release', '-r', action='store', help='The version to release')
    type_group.add_argument('--snapshot', '-s', action='store_true',
                            help="Release a snapshot version (push tags with git sha and updates 'latest').")

    args = parser.parse_args(sys.argv[1:])

    try:
        for docker_image_dir in args.docker_image_dir:
            organization, repository = _get_docker_image_name(docker_image_dir)
            repo = _get_repo(docker_image_dir)
            if not args.yes and not args.snapshot:
                _check_branch(repo)
            tags = _get_tags(organization, repository)
            hash_tag = repo.head.commit.hexsha[:7]
            if not args.force and hash_tag in tags:
                raise UserMessageException('This version is already released to docker hub')
            docker = _init_docker()
            image = '%s/%s:latest' % (organization, repository)
            _docker_build(docker, args, docker_image_dir, image)

            latest_tag = 'latest-snapshot'
            if not args.snapshot:
                latest_tag = 'latest'
                version = _get_next_version(tags)
                if not args.yes and not args.release:
                    user_version = raw_input('What version number would you like to release (%s): ' % version)
                    if user_version is not '':
                        version = user_version
                if args.release:
                    version = args.release

                if args.tag_once:
                    git_tag = 'release-%s' % (version,)
                else:
                    git_tag = '%s/%s/%s' % (organization, repository, version)

                if git_tag in repo.tags and not args.tag_once:
                    raise UserMessageException('This version is already released, contains a tag in git: %s' % git_tag)

                _docker_push(docker, args, image, version)

                if git_tag not in repo.tags:
                    repo.git.tag(git_tag)
                    repo.git.push('--tags')

            _docker_push(docker, args, image, hash_tag)
            _docker_push(docker, args, image, latest_tag)

    except UserMessageException, e:
        print "ERROR: %s" % e.value
        return 1
