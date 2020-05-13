from covid19_scrapers.utils import *
from covid19_scrapers.scraper import ScraperBase

import fitz
from tabula import read_pdf
from urllib.parse import urljoin

## Backwards compatibility for datetime_fromisoformat for Python 3.6 and below
## Has no effect for Python 3.7 and above
## Reference: https://pypi.org/project/backports-datetime-fromisoformat/
from backports.datetime_fromisoformat import MonkeyPatch
MonkeyPatch.patch_fromisoformat()

import logging


_logger = logging.getLogger('covid19_scrapers')


def get_fl_daily_url():
    fl_disaster_covid_url = 'https://floridadisaster.org/covid19/'
    fl_disaster_covid_soup = url_to_soup(fl_disaster_covid_url)
    daily_url = fl_disaster_covid_soup.find('a', {'title': 'COVID-19 Data - Daily Report Archive'}).get('href')
    if not daily_url:
        raise ValueError('Unable to find Daily Report Archive link')
    return urljoin(fl_disaster_covid_url, daily_url)

def get_fl_report_date(url):
    return datetime.date.fromisoformat(re.search(r'-(2020-\d\d-\d\d)-', url).group(1))

def get_fl_table_area(pdf_data):
    """This finds a bounding box for the Race, Ethnicity table by looking for bounding
    boxes for the words "White" and "Total" (occuring below it) on page 3 of the PDF, 
    and the page's right bound.
    """
    doc = fitz.Document(stream=pdf_data, filetype='pdf')
    page3 = doc[2] # page indexes start at 0 

    white_bbox = None
    for (x0, y0, x1, y1, word, block_no, line_no, word_no) in page3.getText('words'):
        if word == 'White':
            white_bbox = fitz.Rect(x0, y0, x1, y1)

    total_bbox = None
    for (x0, y0, x1, y1, word, block_no, line_no, word_no) in page3.getText('words'):
        if word == 'Total':
            if round(x0) == round(white_bbox.x0) and round(y0) > round(white_bbox.y0):
                total_bbox = fitz.Rect(x0, y0, x1, y1)

    return fitz.Rect(white_bbox.x0, white_bbox.y0, page3.bound().x1, total_bbox.y1)

## Original parsers for Florida tables
def parse_num(val):
    if val:
        return float(val.replace(',', ''))
    return float('nan')

def parse_pct(val):
    if val:
        return float(val[:-1])/100
    return float('nan')

column_names = [
    'Race/ethnicity',
    'Cases', '% Cases',
    'Hospitalizations', '% Hospitalizations',
    'Deaths', '% Deaths'
]

converters = {
    'Cases': parse_num,
    'Hospitalizations': parse_num,
    'Deaths': parse_num,
    '% Cases': parse_pct,
    '% Hospitalizations': parse_pct,
    '% Deaths': parse_pct,
}

class Florida(ScraperBase):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
    def _scrape(self, validation, refresh=True):
        _logger.debug('Find daily Florida URL')
        fl_daily_url = get_fl_daily_url()
        _logger.debug(fl_daily_url)

        _logger.debug('Download the daily Florida URL')
        fl_pdf_data = get_content(fl_daily_url, refresh)
      
        _logger.debug('Find the table area coordinates')
        table_bbox = get_fl_table_area(fl_pdf_data)
        table_area = (table_bbox.y0, table_bbox.x0, table_bbox.y1, table_bbox.x1)
        
        _logger.debug('Parse the PDF')
        table = as_list(
            read_pdf(BytesIO(fl_pdf_data),
                     pages='3',
                     stream=True,
                     multiple_tables=False,
                     area=table_area,
                     pandas_options=dict(
                         header=None,
                         names=column_names,
                         converters=converters)))[0]

        
        _logger.debug('Find the report date')
        report_date = get_fl_report_date(fl_daily_url).strftime('%m/%d/%Y')
        
        _logger.debug('Set the race/ethnicity indices')
        races = ('White', 'Black', 'Other', 'Unknown race', 'Total')
        for idx, row in table.iterrows():
            if row['Race/ethnicity'] in races:
                race = row['Race/ethnicity']
                ethnicity = 'All ethnicities'
            else:
                ethnicity = row['Race/ethnicity']
            table.loc[idx, 'Race'] = race
            table.loc[idx, 'Ethnicity'] = ethnicity
        
        table = table.drop('Race/ethnicity', axis=1)
        table = table.set_index(['Race','Ethnicity'])
        
        _logger.debug('Fill NAs?')
        table.loc[('Total', 'All ethnicities')] = table.loc[('Total', 'All ethnicities')].fillna(1)

        att_names = ['Cases', 'Deaths']
        fl_all_cases_and_deaths = {nm: int(table.query("Race == 'Total' and Ethnicity == 'All ethnicities'")[nm].to_list()[0]) for nm in att_names}
        fl_aa_cases_and_deaths = {nm: int(table.query("Race == 'Black' and Ethnicity == 'Non-Hispanic'")[nm].to_list()[0]) for nm in att_names}
        fl_aa_cases_and_deaths_pct = {nm: round(100 * fl_aa_cases_and_deaths[nm] / fl_all_cases_and_deaths[nm], 2)  for nm in att_names}

        return [self._make_series(
            date=report_date,
            cases=fl_all_cases_and_deaths['Cases'],
            deaths=fl_all_cases_and_deaths['Deaths'],
            aa_cases=fl_aa_cases_and_deaths['Cases'],
            aa_deaths=fl_aa_cases_and_deaths['Deaths'],
            pct_aa_cases=fl_aa_cases_and_deaths_pct['Cases'],
            pct_aa_deaths=fl_aa_cases_and_deaths_pct['Deaths'],
        )]