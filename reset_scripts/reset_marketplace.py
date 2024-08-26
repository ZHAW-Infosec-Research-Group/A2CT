import subprocess
import time

subprocess.run('docker stop marketplace', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # prints 'marketplace' if not silenced
subprocess.run('docker rm marketplace', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # prints 'marketplace' if not silenced
subprocess.run('docker compose -f microservices/testapps/marketplace/docker-compose.yml up -d', stderr=subprocess.DEVNULL, shell=True)
time.sleep(5)
