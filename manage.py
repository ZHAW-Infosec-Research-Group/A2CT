#!/usr/bin/env python3
'''
manage.py: Python script to manage the A2CT environment

CLI Usage:
    -h, --help                                     Shows help message
    container       {remove,rm}                    Remove crawler containers
    build image     container_name*                Build docker images

* from the following list: {mitmproxy,playwright-js}

Functions:
    remove_docker_containers()
    build_docker_image()
    main()
'''
import argparse
import subprocess

parser = argparse.ArgumentParser()
subparser = parser.add_subparsers(dest='command', required=True)

container = subparser.add_parser('container')
build = subparser.add_parser('build')

container.add_argument('container_command', help='Remove the containers mitmproxy and playwright-js', choices=['remove', 'rm'])

build.add_argument('build_command', help='Build docker images', choices=['image'])
build.add_argument('container_name', help='Container to build', choices=['mitmproxy', 'playwright-js'])


# Removes the crawler containers originating from the given docker image name
def remove_docker_containers(image_name):
    print(f'Removing containers from image \'{image_name}\'')
    subprocess.run(f'docker rm $(docker stop $(docker ps -a -q --filter ancestor={image_name}))', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def build_docker_image(tag, dockerfile, path):
    # Using the docker SDK would work for building the image, but the build log of the docker image has to
    # be printed manually and the path of the docker file has to be given in absolute form somehow, which
    # makes it preferable to just call the docker binary.
    subprocess.run(['docker', 'build', '-t', tag, '-f', dockerfile, path], check=True)


def main():
    args = parser.parse_args()

    # manage.py container
    if args.command == 'container':
        if args.container_command:
            remove_docker_containers('a2ct/mitmproxy')
            remove_docker_containers('a2ct/playwright-js')

    # manage.py build
    elif args.command == 'build':
        if args.build_command == 'image':
            if args.container_name == 'mitmproxy':
                build_docker_image('a2ct/mitmproxy', 'microservices/crawler/mitmproxy/Dockerfile', 'microservices/crawler/mitmproxy/')
            elif args.container_name == 'playwright-js':
                build_docker_image('a2ct/playwright-js', 'microservices/crawler/playwright-js/Dockerfile', 'microservices/crawler/playwright-js/')


if __name__ == '__main__':
    main()
