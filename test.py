###
# Copyright (c) 2013, Taede Werkhoven
# All rights reserved.
#
#
###

from supybot.test import *

class OttdAdminTestCase(PluginTestCase):
    plugins = ('OttdAdmin',)

    def testRandom(self):
        # difficult to test, let's just make sure it works
        self.assertNotError('random')

    def testSeed(self):
        # just make sure it works
        self.assertNotError('seed 20')

    def testSample(self):
        self.assertError('sample 20 foo')
        self.assertResponse('sample 1 foo', 'foo')
        self.assertRegexp('sample 2 foo bar', '... and ...')
        self.assertRegexp('sample 3 foo bar baz', '..., ... and ...')

    def testDiceRoll(self):
        self.assertActionRegexp('diceroll', 'rolls a \d')

    def testSeedActuallySeeds(self):
        # now to make sure things work repeatably
        self.assertNotError('seed 20')
        m1 = self.getMsg('random')
        self.assertNotError('seed 20')
        m2 = self.getMsg('random')
        self.failUnlessEqual(m1, m2)
        m3 = self.getMsg('random')
        self.failIfEqual(m2, m3)

# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
