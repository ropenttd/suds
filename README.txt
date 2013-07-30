Soap, a Supybot Pluging for communicating with OpenTTD servers via its AdminPort
This plugin is released under the GPL, a copy of which can be found in
COPYING.txt

web: http://dev.openttdcoop.org/projects/soap/
IRC: I can usually be found in #openttd on OFTC

Prerequisites:
 Openttd server
 Supybot set up in a channel
 libottdadmin2 by xaroth installed

 If you don't have OpenTTD installed, you probably won't need this plugin. I
 recommend you download it and play some at www.openttd.org. Come back when you
 are running a dedicated server which you want to administer from irc.

 Supybot comes with its own installation instructions and user manual and can be
 found here: http://sourceforge.net/projects/supybot/

Installing libottdadmin2:
 First go to https://github.com/Xaroth/libottdadmin2 and either download the zip
 or git clone. Now there are 2 ways you can install this lib:

 The first one is the easiest one, run 'python2 setup.py install' from the
 libottdadmin2 dir. This will install the lib systemwide and make it available
 to any other python programs that may need it. You may need root access
 depending on the system setup though.

 The other way is to copy the libottdadmin2 dir into the Soap plugin directory.
 Copied right client.py should be found at this path:
 PathToPlugins/Soap/libottdadmin2/client.py
 This will give the same functionality, but only for the Soap plugin. On the
 upside, no root access required.

Commands:
 apconnect       - connects to the preconfigured openttd server
 apdisconnect    - disconnects from same
 more to be added

Todo:
 chat bridge
 rcon commands
 pause and related stuff
 screenshots
 and loads more