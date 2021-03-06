from io import BytesIO
import logging
import re

import pandas as pd
import requests

from covid19_scrapers.scraper import ScraperBase
from covid19_scrapers.utils.arcgis import query_geoservice


_logger = logging.getLogger(__name__)


class NewJersey(ScraperBase):
    """NOT DONE: New Jersey publishes total COVID-19 case and death counts
    via an ArcGIS, but the demographic breakdowns appear only to be
    available in a Tableau dashboard.
    """

    BETA_SCRAPER = True
    # ArcGIS service is at https://services7.arcgis.com/Z0rixLlManVefxqY
    TOTALS = dict(
        flc_id='24f4fcf164ad4b4280f08c8939dd5dc7',
        layer_name='CaseCounts06272020',
        out_fields=['sum(TOTAL_CASES) as TOTAL_CASES',
                    'sum(TOTAL_DEATHS) as TOTAL_DEATHS'],
    )

    RACE_MAIN_PAGE = 'https://public.tableau.com/views/UnderlyingCauses/COVID-19DeathsbyRace?%3Aembed=y&%3AshowVizHome=no&%3Adisplay_count=y&%3Adisplay_static_image=y&%3AbootstrapWhenNotified=true&%3Alanguage=en&:embed=y&:showVizHome=n&:apiID=host0'
    DEATHS_RACE_URL_TEMPLATE = 'https://public.tableau.com/vizql/w/UnderlyingCauses/v/COVID-19DeathsbyRace/vudcsv/sessions/{session_id}/views/7713620505763405234_13286885388891394922?underlying_table_id=Migrated%20Data&underlying_table_caption=Full%20Data'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def name(self):
        return 'New Jersey'

    def _scrape(self, **kwargs):
        # Get totals date
        date, totals = query_geoservice(self.TOTALS)
        _logger.info(f'Processing data for {date}')
        total_cases = totals.loc[0, 'TOTAL_CASES']
        total_deaths = totals.loc[0, 'TOTAL_DEATHS']

        # No AA case data
        # TODO: find AA case data
        aa_cases = float('nan')
        aa_cases_pct = float('nan')

        # Download the deaths data
        # First load the main page to get a session ID
        s = requests.Session()
        r = s.get(self.RACE_MAIN_PAGE)
        r.raise_for_status()
        _logger.info(f'Tableau session ID is {r.headers["x-session-id"]}')
        # Prepare the data download URL and retrieve
        r = s.get(self.DEATHS_RACE_URL_TEMPLATE.format(
            session_id=r.headers['x-session-id']))
        r.raise_for_status()
        # Load the data into a DataFrame
        deaths = pd.read_csv(BytesIO(r.content))

        n_col = deaths.columns[1]
        total_deaths = int(re.search(r'\d+', n_col).group(0))
        aa_row = deaths[deaths['Race/Ethnicity1'].str.search('Black')]
        aa_deaths = aa_row[n_col]
        aa_deaths_pct = round(100 * aa_row['Percent (Race)'], 2)

        return [self._make_series(
            date=date,
            cases=total_cases,
            deaths=total_deaths,
            aa_cases=aa_cases,
            aa_deaths=aa_deaths,
            pct_aa_cases=aa_cases_pct,
            pct_aa_deaths=aa_deaths_pct,
            pct_includes_unknown_race=False,
            pct_includes_hispanic_black=False,
        )]
