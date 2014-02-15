# PyAlgoTrade
#
# Copyright 2011-2013 Gabriel Martin Becedillas Ruiz
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
.. moduleauthor:: Jesse White <jwhite08@gmail.com>
"""

from pyalgotrade.broker import backtesting
from pyalgotrade.vtrader import VtraderBroker
import testcases.broker_backtesting_test as backtesting_test

from threading import Thread
from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning
from mock_vtrader_site import VtraderBrokerSite

# Set the log level to WARN for testing
import pyalgotrade.logger
import logging
logger = pyalgotrade.logger.getLogger("vtrader.client")
logger.setLevel(logging.WARN)

def tearDownModule():
    reactor.callFromThread(reactor.stop)

class BacktestingBroker(backtesting.Broker):
    def __init__(self, cash, barFeed, commission=None):
        super(BacktestingBroker, self).__init__(cash, barFeed, commission)

    def onBars(self, dateTime, bars):
        super(BacktestingBroker, self).onBars(dateTime, bars)
        self.vtrader.updateActiveOrders()

class VtraderBrokerTestCase(object):
    PortfolioName = "test"
    PortfolioUsername = "testuser"
    PortfolioPassword = "testpass"

    def buildBarFeed(self, *args, **kwargs):
        return backtesting_test.BarFeed(*args, **kwargs)

    def buildBroker(self, *args, **kwargs):
        """ Returns both a VirtualTraderBroker and a BacktestingBroker.
            The VirtualTraderBroker interfaces with a mock webservice that is backed
            by the BacktestingBroker.
        """
        # Create a backtesting broker used to back the mock server
        backtest = BacktestingBroker(*args, **kwargs)

        # Create a new site instance
        site = VtraderBrokerSite(self.PortfolioUsername, self.PortfolioPassword, self.PortfolioName, backtest)

        # Add the new site
        self.port = reactor.listenTCP(0, site)

        # Fire up the reactor
        Thread(target=self.runReactor).start()

        # Create a broker pointing to the new site instance
        url = "http://127.0.0.1:%d" % self.port.getHost().port
        vtrader = VtraderBroker(self.PortfolioName,
                                self.PortfolioUsername, self.PortfolioPassword,
                                url, save_cookies_to_disk=False)
        vtrader.setCommission(kwargs.get('commission', None))

        # Store the ref to the backtest
        vtrader.backtest = backtest

        # And store a ref to the vtrader
        backtest.vtrader = vtrader

        return vtrader

    def runReactor(self):
        try:
            reactor.run(False)
        except ReactorAlreadyRunning:
            pass

class BrokerTestCase(VtraderBrokerTestCase, backtesting_test.BrokerTestCase):
    def testOneCancelsAnother(self):
        # This test doesn't work since the order ids are not set until dispatchBars is called
        pass

#
# Different codes paths are used when handling stocks vs options, so
# we verify these separately
#

class MarketOrderTestCaseWithStock(VtraderBrokerTestCase, backtesting_test.MarketOrderTestCase):
    def setUp(self):
        backtesting_test.BaseTestCase.TestInstrument = 'BB'

    def testBuy_GTC(self):
        # Market orders do not support GTC
        pass

class LimitOrderTestCaseWithStock(VtraderBrokerTestCase, backtesting_test.LimitOrderTestCase):
    def setUp(self):
        backtesting_test.BaseTestCase.TestInstrument = 'BB'

class StopOrderTestCaseWithStock(VtraderBrokerTestCase, backtesting_test.LimitOrderTestCase):
    def setUp(self):
        backtesting_test.BaseTestCase.TestInstrument = 'BB'

class MarketOrderTestCaseWithOption(VtraderBrokerTestCase, backtesting_test.MarketOrderTestCase):
    def setUp(self):
        backtesting_test.BaseTestCase.TestInstrument = 'BB140322C10.00'

    def testBuy_GTC(self):
        # Market orders do not support GTC
        pass

class LimitOrderTestCaseWithOption(VtraderBrokerTestCase, backtesting_test.LimitOrderTestCase):
    def setUp(self):
        backtesting_test.BaseTestCase.TestInstrument = 'BB140322C10.00'

class StopOrderTestCaseWithOption(VtraderBrokerTestCase, backtesting_test.LimitOrderTestCase):
    def setUp(self):
        backtesting_test.BaseTestCase.TestInstrument = 'BB140322C10.00'
