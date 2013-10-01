###
# This file is part of Soap.
#
# Soap is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation, version 2.
#
# Soap is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR
# A PARTICULAR PURPOSE.
#
# See the GNU General Public License for more details. You should have received
# a copy of the GNU General Public License along with Soap. If not, see
# <http://www.gnu.org/licenses/>.
###

import supybot.ircdb as ircdb
import supybot.ircmsgs as ircmsgs
import supybot.ircutils as ircutils

import logging
import logging.handlers
import os.path
import subprocess
import urllib2

from enums import *

def checkIfRunning(gamedir):
    pidfilename = gamedir + 'openttd.pid'
    executable = 'openttd'

    try:
        with open(pidfilename) as pidfile:
            pid = pidfile.readline()
    except IOError:
        return False
    ps = subprocess.Popen('ps -A', shell=True, stdout=subprocess.PIPE)
    output = ps.stdout.read()
    ps.stdout.close()
    ps.wait()
    for line in output.split('\n'):
        if line != '' and line != None:
            fields = line.split()
            pspid = fields[0]
            pspname = fields[3]
            if (pspid == pid) and (executable == pspname):
                return True
    else:
        return False

def checkPermission(irc, msg, channel, allowOps):
    capable = ircdb.checkCapability(msg.prefix, 'trusted')
    if capable:
        return True
    else:
        opped = msg.nick in irc.state.channels[channel].ops
        if opped and allowOps:
            return True
        else:
            return False

def disconnect(conn, forced):
    if forced:
        conn.force_disconnect()
    else:
        conn.disconnect()

def downloadFile(url, directory):
    try:
        f = urllib2.urlopen(url)
        savefile = os.path.join(directory, os.path.basename(url))
        with open(savefile, "wb") as local_file:
            local_file.write(f.read())
    except urllib2.HTTPError, e:
        return (e.code, url)
    except urllib2.URLError, e:
        return (e.reason, url)
    return savefile

def getConnection(connections, channels, source, serverID = None):
    conn = None

    if serverID == None:
        if ircutils.isChannel(source) and source in channels:
            conn = connections.get(source)
    else:
        if ircutils.isChannel(serverID):
            conn = connections.get(serverID)
        else:
            for c in connections.itervalues():
                if c.ID.lower() == serverID.lower():
                    conn = c
    return conn

def getLatestAutoSave(autosavedir):
    max_mtime = 0
    save = None
    for fname in os.listdir(autosavedir):
        if fname.startswith('autosave'):
            fullpath = os.path.join(autosavedir, fname)
            mtime = os.stat(fullpath).st_mtime
            if mtime > max_mtime:
                max_mtime = mtime
                save = fullpath
    return save

def initLogger(conn, logfile):
    if os.path.isdir(logfile):
        conn.logger = logging.getLogger('Soap-%s' % conn.channel)
        if not len(conn.logger.handlers):
            logfile = os.path.join(logfile, '%s.log' % conn.channel)
            logformat = logging.Formatter('%(asctime)s %(message)s')
            handler = logging.handlers.RotatingFileHandler(logfile, backupCount = 2)
            handler.setFormatter(logformat)
            conn.logger.addHandler(handler)
        conn.logger.setLevel(logging.INFO)
    else:
        conn.logger = None

def logEvent(logger, message):
    try:
        logger.info(message)
    except AttributeError:
        pass

def msgChannel(irc, channel, msg):
    if channel in irc.state.channels or irc.isNick(channel):
        irc.queueMsg(ircmsgs.privmsg(channel, msg))

def moveToSpectators(irc, conn, client):
    text = '%s: Please change your name before joining/starting a company' % client.name
    command = 'move %s 255' % client.id

    conn.send_packet(AdminRcon, command = command)
    conn.send_packet(AdminChat,
        action = Action.CHAT,
        destType = DestType.BROADCAST,
        clientID = ClientID.SERVER,
        message = text)
    msgChannel(irc, conn.channel, text)

def refreshConnection(connections, registeredConnections, conn):
    try:
        del registeredConnections[conn.filenumber]
    except KeyError:
        pass
    newconn = conn.copy()
    connections[conn.channel] = newconn
    return newconn

def startServer(gamedir, parameters, log):
    running = checkIfRunning(gamedir)

    if running:
        return ServerStartStatus.ALREADYRUNNING

    pidfilename = os.path.join(gamedir, 'openttd.pid')
    executable = os.path.join(gamedir, 'openttd')
    config = os.path.join(gamedir, 'openttd.cfg')
    autosavedir = os.path.join(gamedir, 'save/autosave/')
    lastsave = getLatestAutoSave(autosavedir)

    command = []
    command.append(executable)
    command.extend(['-D', '-f', '-c', config])
    if not lastsave == None and os.path.isfile(lastsave):
        command.extend(['-g', lastsave])
    if not parameters == 'None':
        command.extend(parameters)

    commandtext = ''
    for item in command:
        commandtext += item + ' '
    log.info('executing: %s' % commandtext)

    try:
        game = subprocess.Popen(command, shell=False, stdout=subprocess.PIPE)
        output = game.stdout.read()
        game.stdout.close()
        game.wait()
    except OSError as e:
        return ServerStartStatus.FAILOSERROR
    except Exception as e:
        log.info('Except triggered: %s' % sys.exc_info()[0])
        return ServerStartStatus.FAILUNKNOWN

    pid = None
    for line in output.split('\n'):
        log.info('OpenTTD output: %s' % line)
        if 'Forked to background with pid' in line:
            words = line.split()
            pid = words[6]
            try:
                with open(pidfilename, 'w') as pidfile:
                    pidfile.write(str(pid))
            except:
                log.info('pidfile error: %s' % sys.exc_info()[0])
                return ServerStartStatus.SUCCESSNOPIDFILE
            return ServerStartStatus.SUCCESS
    return ServerStartStatus.FAILNOPID
