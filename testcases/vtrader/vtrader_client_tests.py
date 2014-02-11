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

import unittest
import datetime
from pyalgotrade.vtrader import client

class InstrumentTestCase(unittest.TestCase):
    def testInstrumentFromSymbol(self):
        stock = client.Instrument.fromSymbol('BB')
        self.assertTrue(isinstance(stock, client.Stock))
        self.assertEqual(stock.getSymbol(), 'BB')
        self.assertEqual(stock.getClassSymbol(), 'BB')

        option = client.Instrument.fromSymbol('BB140322C10.00')
        self.assertTrue(isinstance(option, client.Option))
        self.assertEqual(option.getSymbol(), 'BB140322C10.00')
        self.assertEqual(option.getUnderlying(), stock)
        self.assertTrue(option.isCall())
        self.assertFalse(option.isPut())
        self.assertEqual(option.getStrike(), 10.00)
        self.assertEqual(option.getExpiry(), datetime.date(2014, 03, 22))

        option = client.Instrument.fromSymbol('BB130621P11.00')
        self.assertTrue(isinstance(option, client.Option))
        self.assertEqual(option.getSymbol(), 'BB130621P11.00')
        self.assertEqual(option.getUnderlying(), stock)
        self.assertTrue(option.isPut())
        self.assertFalse(option.isCall())
        self.assertEqual(option.getStrike(), 11.00)
        self.assertEqual(option.getExpiry(), datetime.date(2013, 06, 21))
