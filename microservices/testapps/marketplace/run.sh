set -m
npm run marketplace &
PROC_ID=$!
echo $PROC_ID

until curl --output /dev/null --silent --head --insecure --fail https://127.0.0.1:3443/; do
    printf '.'
    sleep 1
done
sleep 5
printf 'server up'
curl --data 'username=alice&password=rabbit' -v --silent --insecure https://127.0.0.1:3443/login 2>&1 | echo -e "\nCOOKIE;alice;Rolle sales;$(grep 'Set-Cookie' | cut -d ':' -f 2 | cut -d ';' -f 1 | xargs)"
curl --data 'username=john&password=wildwest' -v --silent --insecure https://127.0.0.1:3443/login 2>&1 | echo -e "\nCOOKIE;john;Rolle sales;$(grep 'Set-Cookie' | cut -d ':' -f 2 | cut -d ';' -f 1 | xargs)"
curl --data 'username=robin&password=arrow' -v --silent --insecure https://127.0.0.1:3443/login 2>&1 | echo -e "\nCOOKIE;robin;Rolle marketing;$(grep 'Set-Cookie' | cut -d ':' -f 2 | cut -d ';' -f 1 | xargs)"
curl --data 'username=robin2&password=arrow' -v --silent --insecure https://127.0.0.1:3443/login 2>&1 | echo -e "\nCOOKIE;robin2;Rolle marketing;$(grep 'Set-Cookie' | cut -d ':' -f 2 | cut -d ';' -f 1 | xargs)"
curl --data 'username=donald&password=daisy' -v --silent --insecure https://127.0.0.1:3443/login 2>&1 | echo -e "\nCOOKIE;donald;Rolle productmanager;$(grep 'Set-Cookie' | cut -d ':' -f 2 | cut -d ';' -f 1 | xargs)"
curl --data 'username=luke&password=force' -v --silent --insecure https://127.0.0.1:3443/login 2>&1 | echo -e "\nCOOKIE;luke;Rolle productmanager;$(grep 'Set-Cookie' | cut -d ':' -f 2 | cut -d ';' -f 1 | xargs)"

fg