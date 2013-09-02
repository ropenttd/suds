Soap, a Supybot Pluging for communicating with OpenTTD servers via its AdminPort
This plugin is released under the GPL, a copy of which can be found in
COPYING.txt

web: http://dev.openttdcoop.org/projects/soap/
IRC: I can usually be found in #openttd on OFTC



Prerequisites:
 * Openttd server
 * Supybot set up in a channel
 * libottdadmin2 by Xaroth installed

 If you don't have OpenTTD installed, you probably won't need this plugin. I
 recommend you download it and play some at www.openttd.org. Come back when you
 are running a dedicated server which you want to administer from irc.

 Supybot comes with its own installation instructions and user manual and can be
 found here: http://sourceforge.net/projects/supybot/



Installation and configuration

 To install Soap, simply copy the Soap directory into the bots plugin directory,
 and load the plugin once the bot is running.



Installing libottdadmin2:
 First go to https://github.com/Xaroth/libottdadmin2 and either download the zip
 or git clone. Now there are 2 ways you can install this lib:

 The first one is the easiest one, run 'python2 setup.py install' from the
 libottdadmin2 dir. This will install the lib systemwide and make it available
 to any other python programs that may need it. You may need sudo access
 depending on the system setup though.

 The other way is to copy the libottdadmin2 dir into the Soap plugin directory.
 Copied right client.py should be found at this path:
 <PathToPlugins>/Soap/libottdadmin2/client.py
 This will give the same functionality, but only for the Soap plugin. On the
 upside, no sudo access required.



Configuration

 Configuration is handled via supybot's config command. First thing you want to
 configure is the default settings. Soap can handle multiple game-servers, but
 is bound to 1 server per irc-channel.

 Correct format for config would be:
    config supybot.plugins.Soap.<setting> <value>

 For instance:
    config supybot.plugins.Soap.host 127.0.0.1

 This will set the default for any new server to 127.0.0.1

 To change a setting for one server only, you want to specify the channel:
    config channel [#yourchan] supybot.plugins.Soap.<setting> <value>

 #yourchannel is optional when used in the channel (it will use the current
 channel), but required when used in queries. You'll want to use the latter for
 setting the password.

 Example:
    config channel #mychannel supybot.plugins.Soap.host 127.0.0.1

 can be used anywhere the bot is, whilst:
    config channel supybot.plugins.Soap.host 127.0.0.1

 will change the host for channel the command was issued in.

 Finally, you want to activate the channels by configuring the list of
 channels. This is a global value, so theres only one variation:
    config supybot.plugins.Soap.channels #mychannel #myotherchannel ...

 That will enable below commands for servers tied to those channels. If you
 didn't specify any settings for a channel, it will pick the default setting instead.

 For a description of the individual variables, open config.py with a text editor.



Commands:
 apconnect(*)       - connects to the preconfigured openttd server(*)
 apdisconnect(*)    - disconnects from same
 pause(*)           - manually pauses the game
 unpause(*)         - manually unpauses the game (sets min_active_clients to 0)
 auto(*)            - turns on autopause, and re-sets min_active_clients to the
                       configured amount
 rcon(*)            - sends an rcon command to the server
 clients            - lists the clients connected to the server
 companies          - lists companies
 date               - returns the ingame date
 ding               - should be ping, but that command was taken. Dings the server

 These commands can also be called with channel or serverID as parameter. This can
 be handy when you want to command a server from a different channel or from
 private message.
 Commands marked with (*) require being opped or trusted (depending on allowOps).



Todo:
 screenshots
 password rotation
 file-based stuff (updating/starting openttd etc)



Credits:
 Taede Werkhoven: For writing the plugin
 Xaroth: For writing libottdadmin2, which also served as an example for Soap