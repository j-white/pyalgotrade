__author__ = 'jwhite'

import testcases.broker_common as common
from twisted.internet import reactor
from twisted.internet.error import ReactorAlreadyRunning
from mock_vtrader_server import VtraderBrokerSite
from pyalgotrade.broker import backtesting
from pyalgotrade.vtrader import VtraderBroker
from threading import Thread

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
        site = VtraderBrokerSite(self.PortfolioName, backtest)

        # Add the new site
        self.port = reactor.listenTCP(0, site)

        # Fire up the reactor
        Thread(target=self.runReactor).start()

        # Create a broker pointing to the new site instance
        vtrader = VtraderBroker(self.PortfolioName, self.PortfolioUsername, self.PortfolioPassword,
                             "http://127.0.0.1:%d" % self.port.getHost().port, commission=commission)

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

class VtraderBrokerTestCase:
    Factory = BacktestBrokerFactory()
    Visitor = BacktestBrokerVisitor()

class BrokerTestCase(VtraderBrokerTestCase, common.BrokerTestCase):
    pass

class MarketOrderTestCase(VtraderBrokerTestCase, common.MarketOrderTestCase):
    pass

class LimitOrderTestCase(VtraderBrokerTestCase, common.LimitOrderTestCase):
    pass

class StopOrderTestCase(VtraderBrokerTestCase, common.StopOrderTestCase):
    pass

class StopLimitOrderTestCase(VtraderBrokerTestCase, common.StopLimitOrderTestCase):
    pass
