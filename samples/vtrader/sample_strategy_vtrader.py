from pyalgotrade.vtrader import VtraderStrategy, utils
from datetime import date, timedelta
from sample_strategy import MyStrategy

class VtraderMyStrategy(MyStrategy, VtraderStrategy):
    def __init__(self, feed, instruments, smaPeriod):
        MyStrategy.__init__(self, feed, instruments, smaPeriod)
        VtraderStrategy.__init__(self, feed, **utils.getConfig())

    def onStart(self):
        self.setPositions(self.getBroker().getStrategyPositions(self))

    def onBars(self, bars):
        # Playback the data until yesterday to populate the SMA filters
        yesterday = date.today() - timedelta(days=1)
        if bars.getDateTime().date() < yesterday:
            return

        # Now trade using yesterdays close prices
        MyStrategy.onBars(self, bars)

# Build the strategy
instruments = ['BB', 'T']
feed = utils.getFeed(instruments, suffix='.TO')
strategy = VtraderMyStrategy(feed, instruments, smaPeriod=30)

# Run the strategy.
strategy.run()
print "Current portfolio value: $%.2f" % strategy.getResult()
