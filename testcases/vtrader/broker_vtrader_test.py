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


from pyalgotrade import broker
from pyalgotrade import bar
from pyalgotrade import barfeed
from pyalgotrade.broker import backtesting

class MyTestCase(VtraderBrokerTestCase, common.BaseTestCase):
    def testBuy_GTC(self):
        brk = self.Factory.getBroker(10, barFeed=barfeed.BaseBarFeed(bar.Frequency.MINUTE))
        barsBuilder = common.BarsBuilder(common.BaseTestCase.TestInstrument, bar.Frequency.MINUTE)

        order = brk.createLimitOrder(broker.Order.Action.BUY, common.BaseTestCase.TestInstrument, 4, 2)
        order.setGoodTillCanceled(True)
        self.assertEqual(order.getFilled(), 0)
        self.assertEqual(order.getRemaining(), 2)

        # Fail to buy (couldn't get specific price).
        cb = common.Callback()
        brk.getOrderUpdatedEvent().subscribe(cb.onOrderUpdated)
        brk.placeOrder(order)
        # Set sessionClose to true test that the order doesn't get canceled.
        self.Visitor.onBars(brk, *barsBuilder.nextTuple(10, 15, 8, 12, sessionClose=True))
        self.assertEqual(order.getFilled(), 0)
        self.assertEqual(order.getRemaining(), 2)
        self.assertTrue(order.isAccepted())
        self.assertEqual(order.getExecutionInfo(), None)
        self.assertEqual(len(brk.getActiveOrders()), 1)
        self.assertEqual(brk.getCash(), 10)
        self.assertEqual(brk.getShares(common.BaseTestCase.TestInstrument), 0)
        self.assertEqual(cb.eventCount, 1)

        # Buy
        cb = common.Callback()
        brk.getOrderUpdatedEvent().subscribe(cb.onOrderUpdated)
        self.Visitor.onBars(brk, *barsBuilder.nextTuple(2, 15, 1, 12))
        self.assertEqual(order.getFilled(), 2)
        self.assertEqual(order.getRemaining(), 0)
        self.assertTrue(order.isFilled())
        self.assertEqual(order.getExecutionInfo().getPrice(), 2)
        self.assertEqual(len(brk.getActiveOrders()), 0)
        self.assertEqual(brk.getCash(), 6)
        self.assertEqual(brk.getShares(common.BaseTestCase.TestInstrument), 2)
        self.assertEqual(cb.eventCount, 1)

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
