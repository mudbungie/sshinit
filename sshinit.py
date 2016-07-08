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
    # There should be one to three arguments. Only the optional root flag can
    # lack an @ sign.
    if not 1 <= len(argv) <= 3:
       raise InputError('Argument list out of range.')
    host = None
    bastion = None
    user = None
    root = False
    print(argv)
    # Skip first(this prog), then host, then bastion.
    for arg in argv[1:]:
        print(arg)
        if arg == '-r' or arg == '--root':
            root = True
        else:
            if host:
                # If you argued more than host and bastion, you're wrong.
                if bastion:
                    raise InputError('Too many arguments.')
                else:
                    bastion = arg
            # Splitting on @, host is last, then user. Err if too many @
            else:
                target = arg.split('@')
                host = target[-1]
                if len(target) == 2:
                    user = target[0]
                elif len(target) > 2:
                    raise InputError
    if not user:
        # We want to have a user defined. It's not technological requirement.
        raise InputError

    return user, host, bastion, root
        
# Makes an SSH key, and puts it into $HOME/.ssh/auto/[target]
def createKey(user, host):
    keydir = environ['HOME'] + '/.ssh/auto'
    keypath = keydir + '/' + user + '@' + host

    # Make sure that we can insert keys...
    makedirs(keydir, exist_ok=True)
    chmod(keydir, 0o700)

    # Actually make it.
    if user:
        target = user + '@' + host
    else:
        target = host
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
        elif user.match(line) or proxy.match(line) or idline.match(line):
            print('Commenting out:', line)
            config[index + start] = '#' + line
        else:
            print('Unmanaged line:', line)
    # In case there is no next host config, just give the file back.
    return config

# Make the config file have a valid entry for this host.
def updateConfig(user, host, bastion):
    conffilename = environ['HOME'] + '/.ssh/config'
    try:
        with open(conffilename, 'r') as conffile:
            config = conffile.readlines()
    except FileNotFoundError:
        config = []

    start = findHostLine(config, host)
    config = commentUntilNextHost(config, start)
    
    # Add the relevant lines for the config.
    config.insert(start, '\n')
    if user:
        userline = '    user ' + user + '\n'
        config.insert(start, userline)
    idline = '    IdentityFile ' + createKey(user, host) + '\n'
    config.insert(start, idline)
    if bastion:
        bastionline = '    ProxyCommand ssh ' + bastion + ' -W ' + host + ':%p\n'
        config.insert(start, bastionline)
    hostline = 'Host ' + host + '\n'
    config.insert(start, hostline)

    with open(conffilename, 'w') as conffile:
        conffile.writelines(config)

    return True

def insertKey(user, host, bastion):
    remoteCommand = 'mkdir .ssh 2> /dev/null; cat >> .ssh/authorized_keys'
    connstring = user+'@'+host
    with open(environ['HOME'] + '/.ssh/auto/' + connstring + '.pub') as pubkey:
        #FIXME Add actual bastion parameters.
        subprocess.call(['ssh', user+'@'+host, remoteCommand], 
            stdin=pubkey)
    print('Key installed.')

if __name__ == '__main__':
    try:
        user, host, bastion, root = handle_args(argv)
        print(user, host, bastion, root)
        #createKey(user, host) # Called in updateConfig
        updateConfig(user, host, bastion)
        insertKey(user, host, bastion)
    except InputError:
        print("usage: ssh-init [-r] TARGET [HOP]")
        
