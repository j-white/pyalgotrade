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

from pyalgotrade import broker
from client import VtraderClient

class VtraderOrder:
    pass

class MarketOrder(broker.MarketOrder, VtraderOrder):
    pass

class LimitOrder(broker.LimitOrder, VtraderOrder):
    pass

class StopOrder(broker.StopOrder, VtraderOrder):
    pass

class StopLimitOrder(broker.StopLimitOrder, VtraderOrder):
    pass

class VtraderBroker(broker.Broker):
    """A Vtrader broker.
    """
    def __init__(self, portfolio, username, password, url):
        broker.Broker.__init__(self)
        self.client = VtraderClient(portfolio, username, password, url)

    def getCash(self):
        """Returns the amount of available buying power in dollars."""
        return self.client.get_cash_value()

    def getShares(self, instrument):
        """Returns the number of shares for an instrument."""
        raise NotImplementedError()

    def getPositions(self):
        """Returns a dictionary that maps instruments to shares."""
        raise NotImplementedError()

    def getActiveOrders(self):
        """Returns a sequence with the orders that are still active."""
        raise NotImplementedError()

    def placeOrder(self, order):
        if order.isInitial():
            self.client.place_order(order)

            # Switch from INITIAL -> SUBMITTED
            # IMPORTANT: Do not emit an event for this switch because when using the position interface
            # the order is not yet mapped to the position and Position.onOrderUpdated will get called.
            order.switchState(broker.Order.State.SUBMITTED)
        else:
            raise Exception("The order was already processed")

    def createMarketOrder(self, action, instrument, quantity, onClose=False):
        return MarketOrder(-1, action, instrument, quantity, onClose)

    def createLimitOrder(self, action, instrument, limitPrice, quantity):
        return LimitOrder(-1, action, instrument, limitPrice, quantity)

    def createStopOrder(self, action, instrument, stopPrice, quantity):
        return StopOrder(-1, action, instrument, stopPrice, quantity)

    def createStopLimitOrder(self, action, instrument, stopPrice, limitPrice, quantity):
        return StopLimitOrder(-1, action, instrument, limitPrice, stopPrice, quantity)

    def cancelOrder(self, order):
        """Requests an order to be canceled. If the order is filled an Exception is raised.

        :param order: The order to cancel.
        :type order: :class:`Order`.
        """
        raise NotImplementedError()
