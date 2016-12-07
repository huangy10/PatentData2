# coding=utf-8
import os
import sys
from tornado import httpclient

proj_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.extend([proj_dir])

from tornado import ioloop, gen

from Patent.load_country_code import load_country_code
from Patent.models import *
from workers import IndexWorker, IndexURLMaker
from log import *


index_num = 1
logger = logging.getLogger()


@gen.coroutine
def start_crawler():
    load_country_code()
    session = new_session()
    countries = session.query(Country).all()
    url_maker = IndexURLMaker(countries=countries)
    futures = []
    httpclient.AsyncHTTPClient.configure(None, defaults=dict(max_client=100))
    logger.info(u"爬虫启动,创建%s个线程" % index_num)
    for i in range(index_num):
        worker = IndexWorker(name="default-%s" % i, url_maker=url_maker, session=session)
        futures.append(worker.go())
    # yield gen.sleep(10000)
    yield futures
    logging.info(u"爬虫完成\n\n\n")


if __name__ == "__main__":
    global index_num
    args = sys.argv[1:]
    if len(args) > 0:
        index_num = int(args[0])
    ioloop.IOLoop.current().run_sync(start_crawler)

