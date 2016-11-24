import os
import requests

from auth import login

domain = "http://global.soopat.com"
url_template = "http://global.soopat.com/Patent/Result?" \
               "SearchWord=SQR:( {country_code} ) GKRQ:( {year} ) &" \
               "PatentIndex={index}&Sort=0&g=212"


def make_url(country_code, year, index):
    return url_template.format(country_code=country_code, year=year, index=index)


def crawler_start(echo_to_file=False):
    cookies = login()
    print cookies
    url = make_url("CN", 2010, 0)
    res = requests.get(url, cookies=cookies)
    if echo_to_file:
        with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "log.html"), "w") as f:
            f.write(res.content)
    return res

if __name__ == '__main__':
    crawler_start()