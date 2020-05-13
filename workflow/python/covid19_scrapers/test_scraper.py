from covid19_scrapers.scraper import SUCCESS, ScraperBase

def test_empty_scraper():
    class EmptyScraper(ScraperBase):
        def _scrape(self, unused1, unused2):
            return []
    scraper = EmptyScraper()
    assert scraper.name() == "EmptyScraper"
    assert scraper.run().empty

def test_one_row_scraper():
    class OneRowScraper(ScraperBase):
        def _scrape(self, unused1, unused2):
            return [self._make_series()]
    scraper = OneRowScraper()
    assert scraper.name() == "OneRowScraper"
    df = scraper.run()
    assert df.shape[0] == 1
    assert df.loc[0, 'Status code'] == SUCCESS

def test_throwing_scraper():
    class ThrowingScraper(ScraperBase):
        def _scrape(self, unused1, unused2):
            raise ValueError('error')
    scraper = ThrowingScraper()
    assert scraper.name() == "ThrowingScraper"
    df = scraper.run()
    assert df.shape[0] == 1
    assert df.loc[0, 'Status code'] == "ERROR: ValueError('error')"

def test_throwing_custom_handler_scraper():
    class ThrowingCustomHandlerScraper(ScraperBase):
        def _scrape(self, unused1, unused2):
            raise ValueError('error')
    
        def _handle_error(self, e):
            return [self._make_series(status='CUSTOM TEXT')] 
    scraper = ThrowingCustomHandlerScraper()
    assert scraper.name() == "ThrowingCustomHandlerScraper"
    df = scraper.run()
    assert df.shape[0] == 1
    assert df.loc[0, 'Status code'] == 'CUSTOM TEXT'

def test_throwing_custom_format_scraper():
    class ThrowingCustomFormatScraper(ScraperBase):
        def _scrape(self, unused1, unused2):
            raise ValueError('error')
    
        def _format_error(self, e):
            return 'CUSTOM TEXT' 
    scraper = ThrowingCustomFormatScraper()
    assert scraper.name() == "ThrowingCustomFormatScraper"
    df = scraper.run()
    assert df.shape[0] == 1
    assert df.loc[0, 'Status code'] == 'CUSTOM TEXT'
