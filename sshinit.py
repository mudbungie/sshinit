#!/usr/bin/python3

# This software is covered under the GNU AGPLv3 
# https://www.gnu.org/licenses/agpl-3.0.en.html
# Contact the author at mudbungie@gmail.com
# Copyright 2016 mudbungie

# Program to initialize an SSH configuration with a host. Makes a new SSH key, 
# copies that to the host, appends the use of that key to the local 
# ~/.ssh/config. If the -r option is invoked, it will also su into the host's
# root user, and copy the ssh key there.

# Usage: 
#   ssh-init [-r] user@host

from sys import argv
import subprocess
import re
from os import environ, chmod, makedirs

# Goes through the list of arguments passed, and returns the target system's
# user, host, whether or not we're providing root access, and an intermediate
# hop, if any.
def handle_args(argv):
    # There should be one to three arguments. Only the optional root flag can
    # lack an @ sign.
    if not 1 <= len(argv) <= 3:
       raise InputError('Argument list out of range.')
    root = False
    target = None
    bastion = None
    for arg in argv[1:]:
        print(arg)
        if arg == '-r' or arg == '--root':
            root = True
        elif '@' in arg:
            if target:
                bastion = arg
            else:
                user, host = arg.split('@')
                target = True
        else:
            raise InputError('Expected username@hostname')
    return user, host, bastion, root
        
class InputError(Exception):
    pass

# Makes an SSH key, and puts it into $HOME/.ssh/auto/[target]
def createKey(user, host):
    keydir = environ['HOME'] + '/.ssh/auto'
    keypath = keydir + '/' + user + '@' + host

    # Make sure that we can insert keys...
    try:
        makedirs(keydir)
        chmod(keydir, 0o700)
    except FileExistsError:
        pass
    subprocess.call(['ssh-keygen','-t','ed25519','-f',keypath,'-C',
        user+'@'+host,'-N',''])
    print('Keypair created in', keypath)
    return True

# Checks the ~/.ssh/config file for existing configuration. Returns line range
# or none.
def findHostLine(config, host):
    hostline = re.compile('^\s*Host\s*' + re.escape(host) + '\s*$')
    for index, line in enumerate(config):
        if hostline.match(line):
            return index
    return len(config)

# Comment out parameters that we set.
def commentUntilNextHost(config, start):
    user = re.compile('^\s*user\s*\w{1,32}\s*$')
    proxy = re.compile('^\s*ProxyCommand')
    anyhostline = re.compile('^\s*Host')
    for line in config[index:]:
        if anyhostline.match(line):
            return config
        if user.match(line) or proxy.match(line):
            line = '#' + line
    return config

# Make the config file have a valid entry for this host.
def updateConfig(host, user, bastion):
    conffilename = environ['HOME'] + '/.ssh/config'
    try:
        with open(conffilename, 'r') as conffile:
            config = conf.readlines()
    except FileNotFoundError:
        config = []

    config = commentUntilNextHost(config, start)

    userline = '    user ' + user
    config.insert(start, userline)
    if bastion:
        config.insert(start, '    ProxyCommand ssh ' + bastion +\
            ' -W ' + host + '%p')
    with open(conffilename, 'w') as conffile:
        conffile.write(config)

    return True

def insertKey(host, user, bastion):
    remoteCommand = "'mkdir .ssh 2> /dev/null; cat >> .ssh/authorized_keys'"
    connstring = user+'@'+host
    with open(environ['HOME'] + '/.ssh/auto/' + connstring + '.pub') as f:
        pubkey = f.read()
    subprocess.call('ssh', user+'@'+host, remotecommand, stdin=pubkey)
    print('Key installed.')

if __name__ == '__main__':
    try:
        user, host, root, bastion = handle_args(argv)
        print(user, host, root, bastion)
        createKey(user, host)
    except InputError:
        print("usage: ssh-init [-r] TARGET [HOP]")
        
