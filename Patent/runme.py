# coding=utf-8
import os
import requests
from tornado import gen, ioloop

from auth import login
from workers import SearchWorker
from models import new_session, Country
from load_country_code import load_country_code

domain = "http://global.soopat.com"
url_template = "http://global.soopat.com/Patent/Result?" \
               "SearchWord=SQR:( {country_code} ) GKRQ:( {year} ) &" \
               "PatentIndex={index}&Sort=0&g=212"


def make_url(country_code, year, index):
    return url_template.format(country_code=country_code, year=year, index=index)


@gen.coroutine
def crawler_start():
    # cookies = login()
    # print cookies
    # url = make_url("CN", 2010, 0)
    # res = requests.get(url, cookies=cookies)
    # if echo_to_file:
    #     with open(os.path.join(os.path.abspath(os.path.dirname(__file__)), "log.html"), "w") as f:
    #         f.write(res.content)
    # return res
    load_country_code()
    session = new_session()
    countries = session.query(Country).all()
    searcher = SearchWorker(name="default", countries=countries, session=session)
    yield searcher.go()
    print "搜索完成"


if __name__ == '__main__':
    io_loop = ioloop.IOLoop.current()
    io_loop.run_sync(crawler_start)
