from pyalgotrade import bar
from pyalgotrade import broker
from broker_vtrader_test import VtraderBrokerTestCase
import testcases.broker_backtesting_test as backtesting_test
from pyalgotrade.vtrader import VtraderStrategy
import unittest
from twisted.internet import reactor

def tearDownModule():
    reactor.callFromThread(reactor.stop)

class StrategyTestCase(VtraderBrokerTestCase, unittest.TestCase):
    def testGetStrategyPositions(self):
        instrument = backtesting_test.BaseTestCase.TestInstrument
        barFeed = self.buildBarFeed(instrument, bar.Frequency.MINUTE)
        brk = self.buildBroker(11, barFeed)

        # Buy
        order = brk.createMarketOrder(broker.Order.Action.BUY, instrument, 1)
        brk.placeOrder(order)
        self.assertEqual(order.getFilled(), 0)
        self.assertEqual(order.getRemaining(), 1)
        barFeed.dispatchBars(10, 15, 8, 12)
        self.assertTrue(order.isFilled())
        self.assertEqual(order.getAvgFillPrice(), 10)
        self.assertTrue(len(brk.getActiveOrders()) == 0)
        self.assertTrue(brk.getCash() == 1)
        self.assertTrue(brk.getShares(instrument) == 1)

        strategy = VtraderStrategy(barFeed, brk)
        positions = brk.getStrategyPositions(strategy)
        self.assertEquals(1, len(positions))
        self.assertTrue(positions[instrument].entryFilled())

        self.assertTrue(len(brk.getActiveOrders()) == 0)
        self.assertTrue(brk.getCash() == 1)
        self.assertTrue(brk.getShares(instrument) == 1)
