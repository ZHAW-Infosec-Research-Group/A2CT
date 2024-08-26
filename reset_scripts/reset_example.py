import subprocess
import time

# Stop docker container(s) of application under test
subprocess.call('docker compose -f <path_to_application>/docker-compose.yml down', shell=True)
# Add wait time for containers to be stopped
time.sleep(2) 
# Reset the application state by deleting the  application's docker volumes containing, e.g., database data
subprocess.call('rm -rf /opt/<application_name>/*', shell=True)
# Restore the application state by copying fresh data into the application folder
subprocess.call('cp -r <path_to_application_data> /opt/<application_name>', shell=True)
# Adjust the permissions of the application data if necessary
subprocess.call("chmod -R 777 /opt/<application_name>", shell=True)
# Start the docker container(s) of the application under test again
subprocess.run('docker compose -f <path_to_application>/docker-compose.yml up -d', shell=True)
# Check for readiness of the application under test or utilize a fixed timer
time.sleep(20) 