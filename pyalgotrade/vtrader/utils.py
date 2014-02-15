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
from pyalgotrade.tools import yahoofinance
from pyalgotrade.barfeed import yahoofeed, sqlitefeed
import os
from datetime import datetime, timedelta
import tempfile
import ConfigParser

import pyalgotrade.logger
logger = pyalgotrade.logger.getLogger("vtrader.utils")

def getHome():
    home = os.path.join(os.path.expanduser("~"), ".pyalgotrade")
    if not os.path.exists(home):
        os.makedirs(home)
    return home

def getConfig():
    # ~/.pyalgotrade/vtrader.cfg should contain something like:
    sample_config = """
    [vtrader]
    portfolio: <YOUR-PORTFOLIO-NAME-HERE>
    username: <YOUR-USERNAME-HERE>
    password: <YOUR-PASSWORD-HERE>
    url: <VTRADER-URL-HERE>
    """

    config = ConfigParser.ConfigParser()
    config.read(os.path.join(getHome(), 'vtrader.cfg'))
    return dict(config.items('vtrader'))

def getFeed(instruments, suffix='', start_date=datetime(2009, 01, 01)):
    frequency = bar.Frequency.DAY
    home = os.path.join(os.path.expanduser("~"), ".pyalgotrade")
    dbFile = os.path.join(home, 'bars.sqlite')
    db_feed = sqlitefeed.Feed(dbFile, frequency)
    db = sqlitefeed.Database(dbFile)

    for instrument in instruments:
        last_bar_time = start_date
        bars = db.getBars(instrument, frequency)
        if len(bars) > 0:
            last_bar_time = bars[-1].getDateTime()
            logger.info("We already have bars for %s up to %s" % (instrument, last_bar_time.strftime('%d/%m/%Y')))

        begin = last_bar_time + timedelta(days=1)
        end = datetime.now() - timedelta(days=1)
        if end.date() >= begin.date():
            logger.info("Downloading bars for %s from %s to %s" % (instrument, begin.strftime('%d/%m/%Y'), end.strftime('%d/%m/%Y')))
            csv = yahoofinance.download_csv(instrument + suffix, begin, end, frequency)
            logger.info("Download complete. Persisting bars to database.")

            tmpfile = tempfile.NamedTemporaryFile(delete=True)
            tmpfile.write(csv)
            tmpfile.flush()

            yahoo_feed = yahoofeed.Feed()
            yahoo_feed.addBarsFromCSV(instrument, tmpfile.name)
            db.addBarsFromFeed(yahoo_feed)

            tmpfile.close()
            logger.info("Done persisting bars to database.")

        db_feed.loadBars(instrument, fromDateTime=start_date)

    return db_feed
