#!/bin/sh

mkdir -p /var/supybot/data/plugins/suds
cp -rf /plugin /var/supybot/data/plugins/suds

if [ "$#" -ne 1 ]
then
    supybot-wizard --allow-root
else
    supybot --allow-root "$1"
fi