from pyalgotrade import bar
from pyalgotrade import broker
from broker_vtrader_test import VtraderBrokerTestCase
import testcases.broker_backtesting_test as backtesting_test
from pyalgotrade.vtrader import VtraderStrategy
import unittest
from twisted.internet import reactor

def tearDownModule():
    reactor.callFromThread(reactor.stop)

class StrategyPositions(VtraderBrokerTestCase, unittest.TestCase):
    def testGetStrategyPositionsWithLong(self):
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
        self.assertEqual(len(brk.getActiveOrders()), 0)
        self.assertEqual(brk.getCash(), 1)
        self.assertEqual(brk.getShares(instrument), 1)

        strategy = VtraderStrategy(barFeed, brk)
        positions = brk.getStrategyPositions(strategy)
        self.assertTrue(instrument in positions)
        self.assertTrue(positions[instrument].entryFilled())
        self.assertEqual(positions[instrument].getShares(), 1)

        self.assertEqual(len(brk.getActiveOrders()), 0)
        self.assertEqual(brk.getCash(), 1)
        self.assertEqual(brk.getShares(instrument), 1)

    def testGetStrategyPositionsWithShort(self):
        instrument = backtesting_test.BaseTestCase.TestInstrument
        barFeed = self.buildBarFeed(instrument, bar.Frequency.MINUTE)
        brk = self.buildBroker(11, barFeed)

        # Short
        order = brk.createMarketOrder(broker.Order.Action.SELL_SHORT, instrument, 1)
        brk.placeOrder(order)
        self.assertEqual(order.getFilled(), 0)
        self.assertEqual(order.getRemaining(), 1)
        barFeed.dispatchBars(10, 15, 8, 12)
        self.assertTrue(order.isFilled())
        self.assertEqual(order.getAvgFillPrice(), 10)
        self.assertEqual(len(brk.getActiveOrders()), 0)
        self.assertEqual(brk.getCash(), 21)
        self.assertEqual(brk.getShares(instrument), -1)

        strategy = VtraderStrategy(barFeed, brk)
        positions = brk.getStrategyPositions(strategy)
        self.assertTrue(instrument in positions)
        self.assertTrue(positions[instrument].entryFilled())
        self.assertEqual(positions[instrument].getShares(), -1)

        self.assertEqual(len(brk.getActiveOrders()), 0)
        self.assertEqual(brk.getCash(), 21)
        self.assertEqual(brk.getShares(instrument), -1)
