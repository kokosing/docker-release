# docker-release

Tool for releasing docker images. It is useful when your docker image files are under continuous development and you want to have a convenient way to release (publish) them.

This utility supports:
 - tagging git repository when a docker image gets released
 - tagging docker image with a git hash commit
 - incrementing docker image version (tag)
 - updating 'latest' tag in the docker hub

## Requirements:

-  git (tested with version 1.9.1)
-  docker (tested with 1.10)
-  python 2.7

## Installation

### Using pypi packages

In order to install docker-release please do the following:

    pip install docker-release

> Note that usage of virtualenv is recommended.
  
## Manual

    git clone git@github.com:kokosing/docker-release.git
    cd docker-release
    python setup.py build
    python setup.py install
  
## Docker image project convention

docker-release project is designed to work seamlessly when docker image files are stored in a following way:

```
.
└── {organization}
    └── {repository}
        ├── Dockerfile
        └─ ... image files ...
```

## Usage

### Making a release

```
docker-release {organization}/{repository}
```

Above command will check if you are on the `master` branch to make sure you are not going to make release from local branch. Then it will rebuild the image locally and release it to docker hub. It will push a docker image with tags:
 - hash of current git commit 
 - next version number (docker hub is consulted to retrieve the list of released versions)
 - latest
In case that a docker image with tag equaled to hash of current git commit is already released, no release will be performed.


### Making a snapshot

```
docker-release -s {organization}/{repository}
```

Above command will rebuild the image locally and release the snapshot to docker hub. It will push a docker image with tags:
 - hash of current git commit 
 - latest
In case that a docker image with tag equaled to hash of current git commit is already released, no release will be performed.
