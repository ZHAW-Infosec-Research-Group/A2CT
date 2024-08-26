#!/bin/bash
dbpath=/opt/mitmproxy/db/responses.db
if [[ -f $dbpath ]]; then 
	mv $dbpath $dbpath.$(date +"%Y-%m-%d-%H-%M")
fi
touch $dbpath
chmod 777 $dbpath
