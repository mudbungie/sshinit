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

class InputError(Exception):
    pass

# Goes through the list of arguments passed, and returns the target system's
# user, host, whether or not we're providing root access, and an intermediate
# hop, if any.
def handle_args(argv):
    # Default settings:
    root = False
    pseudonym = False
    target = False
    bastion = False
    argv = argv[1:] # Discard the name of the program.
    for index, arg in enumerate(argv):
        print(index, arg)
        if arg == '-r':
            root = True
        elif arg == '-p':
            print('it was -p')
            try:
                pseudonym = argv.pop(index + 1)
            except IndexError:
                raise InputError('-p takes a positional argument.')
        # First positional is host.
        elif not target:
            # Check for the presence of a user.
            # This does a basic sanity check.
            targetSplit(arg)
            target = arg
        # Second positional is bastion.
        elif not bastion:
            bastion = arg
        else:
            raise InputError('Too many arguments')
    return target, bastion, root, pseudonym
        
def targetSplit(*args):
    if len(args) == 1:
        host = args[0].split('@')
        if len(host) == 1:
            return False, host[0]
        elif len(host) == 2:
            return host[0], host[1]
        else:
            raise InputError('Too many @ signs in host.')
    elif len(args) == 2:
        return '@'.join([args[0], args[1]])
    else:
        raise IndexError('wrong number of arguments')

# Makes an SSH key, and puts it into $HOME/.ssh/auto/[target]
def createKey(target):
    keydir = environ['HOME'] + '/.ssh/auto'

    # Make sure that we can insert keys...
    makedirs(keydir, exist_ok=True)
    chmod(keydir, 0o700)

    # Actually make it.

    keypath = keydir + '/' + target

    subprocess.call(['ssh-keygen','-t','ed25519','-f',keypath,'-C',
        target,'-N',''])
    print('Keypair created in', keypath)
    return keypath

# Checks the ~/.ssh/config file for existing configuration. Returns line range
# or none.
def findHostLine(config, host):
    hostline = re.compile('^\s*Host\s*' + re.escape(host) + '\s*$')
    for index, line in enumerate(config):
        if hostline.match(line):
            return index
    return len(config)

# Comment out parameters that we set: user, proxy, identityfile, host.
def commentUntilNextHost(config, start):
    user = re.compile(r'^\s*user\s.*$')
    proxy = re.compile(r'^\s*ProxyCommand\s.*')
    idline = re.compile(r'^\s*IdentityFile\s.*')
    hostnameline = re.compile(r'^\s*hostname\s.*')
    anyhostline = re.compile(r'^\s*Host\s.*')

    try:
        config[start] = '#' + config[start]
    except IndexError:
        pass
    # Iterate over lines from start, comment things until you hit nest host. 
    for index, line in enumerate(config[start:]):
        if anyhostline.match(line):
            print('Host match for:', line)
            print('Stopping ssh configuration.')
            return config
        elif user.match(line) or proxy.match(line) or idline.match(line) \
            or hostnameline.match(line):
            print('Commenting out:', line)
            config[index + start] = '#' + line
        else:
            print('Unmanaged line:', line)
    # In case there is no next host config, just give the file back.
    return config

# Make the config file have a valid entry for this host.
def updateConfig(target, bastion, pseudonym, keypath):
    # Just get the config file.
    conffilename = environ['HOME'] + '/.ssh/config'
    try:
        with open(conffilename, 'r') as conffile:
            config = conffile.readlines()
    except FileNotFoundError:
        config = []

    start = findHostLine(config, pseudonym)
    config = commentUntilNextHost(config, start)

    user, host = targetSplit(target)
    
    # Add the relevant lines for the config.
    config.insert(start, '\n')
    if pseudonym:
        hostnameline = '    hostname ' + host + '\n'
        config.insert(start, hostnameline)
    else:
        pseudonym = host
    if user:
        userline = '    user ' + user + '\n'
        config.insert(start, userline)
    idline = '    IdentityFile ' + keypath + '\n'
    config.insert(start, idline)
    if bastion:
        bastionline = '    ProxyCommand ssh ' + bastion + ' -W ' + host + ':%p\n'
        config.insert(start, bastionline)
    hostline = 'Host ' + pseudonym + '\n'
    config.insert(start, hostline)

    with open(conffilename, 'w') as conffile:
        conffile.writelines(config)

    return True

def insertKey(target, keypath, bastion):
    remoteCommand = 'mkdir .ssh 2> /dev/null; cat >> .ssh/authorized_keys'
    with open(environ['HOME'] + '/.ssh/auto/' + target + '.pub') as pubkey:
        #FIXME Add actual bastion parameters.
        subprocess.call(['ssh', target, remoteCommand], 
            stdin=pubkey)
    print('Key installed.')

if __name__ == '__main__':
    try:
        target, bastion, root, pseudonym = handle_args(argv)
        keypath = createKey(pseudonym)
        updateConfig(target, bastion, pseudonym, keypath)
        insertKey(target, keypath, bastion)
    except InputError:
        #print("usage: ssh-init [-r] [-p pseudonym] TARGET [HOP]")
        raise
        
