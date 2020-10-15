#!/usr/bin/env bash
# when debugging in pycharm run with `watch ./pycharm_debugger_port_proxy.sh`
# this keeps pycharm_debugger.yaml up to date and restarts pycharm_debugger_proxy service if pycharm uses a new debugger port

DEBUG_PORT=$(ps fax | grep -v grep | grep /opt/.pycharm_helpers/pydev/pydevd.py | sed 's,.*--port \([0-9]\+\).*,\1,')
if [[ $DEBUG_PORT ]] ; then
    if [[ ! -e pycharm_debugger.yaml ]] ; then
        cp pycharm_debugger.yaml.tmpl pycharm_debugger.yaml
    fi
    sed -i 's/\(- "127.0.0.1:\)[0-9]\+:[0-9]\+\(" #dynamic pycharm debugger port mapping\)/\1'$DEBUG_PORT':'$DEBUG_PORT'\2/;s/\(PORT: "\)[0-9]\+\(" #dynamic pycharm debugger port connection\)/\1'$DEBUG_PORT'\2/' pycharm_debugger.yaml
    docker-compose -f pycharm_debugger.yaml up -d pycharm_debugger_proxy
fi
