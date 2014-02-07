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

from pyalgotrade import bar
from pyalgotrade import broker
from pyalgotrade import barfeed

from mock_vtrader_server import MockVtraderServerTestCase

class MarketOrderTestCase(MockVtraderServerTestCase):
    def testBuyAndSell(self):

        # Buy
        brk = self.get_vtrader_broker(1000, barFeed=barfeed.BaseBarFeed(bar.Frequency.MINUTE))
        self.assertEqual(brk.getCash(), 1000)
        # order = brk.createMarketOrder(broker.Order.Action.BUY, MockVtraderServerTestCase.TestInstrument, 1)
        # brk.placeOrder(order)
