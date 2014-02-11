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
from pyalgotrade.vtrader import VtraderBroker, VtraderClient
import testcases.broker_common as common

from threading import Thread
from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning
from mock_vtrader_site import VtraderBrokerSite

def tearDownModule():
    reactor.callFromThread(reactor.stop)

class BacktestBrokerFactory(common.BrokerFactory):
    PortfolioName = "test"
    PortfolioUsername = "testuser"
    PortfolioPassword = "testpass"

    def getBroker(self, cash, barFeed, commission=None):
        """ Returns both a VirtualTraderBroker and a BacktestingBroker.
            The VirtualTraderBroker interfaces with a mock webservice that is backed
            by the BacktestingBroker.
        """
        # Create a backtesting broker used to back the mock server
        backtest = backtesting.Broker(cash, barFeed, commission=commission)

        # Create a new site instance
        site = VtraderBrokerSite(self.PortfolioUsername, self.PortfolioPassword, self.PortfolioName, backtest)

        # Add the new site
        self.port = reactor.listenTCP(0, site)

        # Fire up the reactor
        Thread(target=self.runReactor).start()

        # Create a broker pointing to the new site instance
        url = "http://127.0.0.1:%d" % self.port.getHost().port
        client = VtraderClient(self.PortfolioName, self.PortfolioUsername,
                               self.PortfolioPassword, url,
                               save_cookies_to_disk=False)
        vtrader = VtraderBroker(self.PortfolioName, self.PortfolioUsername, self.PortfolioPassword, url,
                                client=client, commission=commission)

        # Store the ref to the backtest
        vtrader.backtest = backtest

        return vtrader

    def getFixedCommissionPerTrade(self, amount):
        return backtesting.FixedPerTrade(amount)

    def runReactor(self):
        try:
            reactor.run(False)
        except ReactorAlreadyRunning:
            pass

class BacktestBrokerVisitor(common.BrokerVisitor):
    def onBars(self, broker, dateTime, bars):
        broker.backtest.onBars(dateTime, bars)
        broker.updateActiveOrders()

class VtraderBrokerStockTestCase:
    TestInstrument = 'BB'
    Factory = BacktestBrokerFactory()
    Visitor = BacktestBrokerVisitor()

class VtraderBrokerOptionTestCase:
    TestInstrument = 'BB140322C10.00'
    Factory = BacktestBrokerFactory()
    Visitor = BacktestBrokerVisitor()

class BrokerTestCaseWithStock(VtraderBrokerStockTestCase, common.BrokerTestCase):
    pass

class MarketOrderTestCaseWithStock(VtraderBrokerStockTestCase, common.MarketOrderTestCase):
    pass

class LimitOrderTestCaseWithStock(VtraderBrokerStockTestCase, common.LimitOrderTestCase):
    pass

class StopOrderTestCaseWithStock(VtraderBrokerStockTestCase, common.StopOrderTestCase):
    pass

class BrokerTestCaseWithOption(VtraderBrokerOptionTestCase, common.BrokerTestCase):
    pass

class MarketOrderTestCaseWithOption(VtraderBrokerOptionTestCase, common.MarketOrderTestCase):
    pass

class LimitOrderTestCaseWithOption(VtraderBrokerOptionTestCase, common.LimitOrderTestCase):
    pass

class StopOrderTestCaseWithOption(VtraderBrokerOptionTestCase, common.StopOrderTestCase):
    pass
