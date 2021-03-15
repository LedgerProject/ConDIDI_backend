#!/usr/bin/env sh
cd database
chmod a+x setup.x
./setup.x
cd ..
git clone https://github.com/jolocom/sdk-rpc-interface.git
docker build sdk-rpc-interface/packages/server/
echo "!! Do not forget to copy the config.ini.example to config.ini in the src folder and set the callback url !!"
