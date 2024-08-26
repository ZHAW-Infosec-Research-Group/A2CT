"""
Service to handle Docker containers

Classes:
DockerService
"""


import logging
import docker


class DockerService():
    """ Handle Docker service requests. """
    def __init__(self):
        self.client = docker.from_env()

    def spawn_container(self, image_name, command='', volumes={}, env_variables=[], detached=False, init=False):
        """ Start a Docker container and return either a container object or the output as String.

        Keyword arguments:
        image_name -- Image for the container (required)
        command -- Command to run
        volumes -- Dict of volume mappings for mounting into the container
        env_variables -- List of environment variables to set inside the container
        detached -- Boolean whether the container will be run detached (Default: False)
        init -- Boolean whether to pass init flag to Docker for setting an init process as PID 1

        """

        logging.info(f'Starting Docker container {image_name}')
        result = self.client.containers.run(
            image=image_name,
            command=command,
            volumes=volumes,
            environment=env_variables,
            detach=detached,
            init=init,
            remove=True
        )

        # This is just to make clear that the run method returns either a container object or the container output
        if detached:
            container = result
            return container
        else:
            output = f'Logs from init-crawler/ {image_name} :\n {result}'
            return output

    def write_container_logs(self, container):
        """ Writes the logs of a Docker container to the default log.

        Keyword arguments:
        container -- Either a container object or the log output as String (required)

        """

        if isinstance(container, str):
            logging.debug(container)
        else:
            logs = container.logs()
            logging.debug(f'Logs from {container.image} :\n {logs}')

    def inspect_container(self, container_id):
        """ Return result of docker inspect command for container_id. """
        return self.client.api.inspect_container(container_id)
