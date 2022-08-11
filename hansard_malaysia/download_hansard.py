import urllib.request
import pandas as pd
import time


def download_hansards(start_from="2019-03-11"):
    df = pd.read_csv('sessions.csv', parse_dates=['date'])
    df.date = df.date.dt.date
    sessions = df.session.tolist()
    session_date = dict(zip(df.session, df.date))

    ok = False
    for s in sessions:
        raw_date_string = session_date[s].strftime('%Y-%m-%d')
        print(raw_date_string)
        if not ok:
            if raw_date_string == start_from:
                ok = True
            else:
                continue
        print(s)
        tdate = session_date[s].strftime('%d%m%Y')
        url_hansard = 'https://www.parlimen.gov.my/files/hindex/pdf/DR-' + tdate + '.pdf'
        urllib.request.urlretrieve(url_hansard, 'src_hansard/hansard_' + s + '.pdf')
        time.sleep(10)


if __name__ == "__main__":
    download_hansards('2018-07-16')
