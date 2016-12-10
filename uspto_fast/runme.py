# coding=utf-8
import os
import sys
from tornado import httpclient

proj_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.extend([proj_dir])

from tornado import ioloop, gen

from workers import FullIndexURLMaker, FullIndexWorker
from models import new_session
from uspto.log import *


index_num = 1
logger = logging.getLogger()


@gen.coroutine
def start_crawler():
    session = new_session()
    url_maker = FullIndexURLMaker()
    futures = []
    httpclient.AsyncHTTPClient.configure(None, defaults=dict(max_client=100))
    logger.info(u"爬虫启动,创建%s个线程" % index_num)
    for i in range(index_num):
        worker = FullIndexWorker(name="default-%s" % i, url_maker=url_maker, session=session)
        futures.append(worker.go())
    # yield gen.sleep(10000)
    yield futures
    logging.info(u"爬虫完成\n\n\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) > 0:
        index_num = int(args[0])
    ioloop.IOLoop.current().run_sync(start_crawler)
