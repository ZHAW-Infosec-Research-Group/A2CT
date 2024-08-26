"""
Tests for docker_service.py
"""


from modules.docker_service import DockerService


def test_spawn_container():
    docker_service = DockerService()
    result = docker_service.spawn_container(image_name="debian:9-slim", command="uname")
    assert 'Linux' in str(result)


def test_inspect_container():
    docker_service = DockerService()
    result = docker_service.spawn_container("debian:9-slim", "uname", detached=True)
    container_properties = docker_service.inspect_container(result.id)
    assert isinstance(container_properties['NetworkSettings']['Networks']['bridge']['IPAddress'], str)
