import os
import sys

proj_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.extend([proj_dir])
print proj_dir

from tornado import ioloop, gen

from Patent.load_country_code import load_country_code
from Patent.models import *
from workers import IndexWorker, IndexURLMaker


index_num = 1

@gen.coroutine
def start_crawler():
    load_country_code()
    session = new_session()
    countries = session.query(Country).all()
    url_maker = IndexURLMaker(countries=countries)
    futures = []
    for i in range(index_num):
        worker = IndexWorker(name="default-%s" % i, url_maker=url_maker, session=session)
        futures.append(worker.go())
    # yield gen.sleep(10000)
    yield futures


if __name__ == "__main__":
    global index_num
    args = sys.argv[1:]
    if len(args) > 0:
        index_num = int(args[0])
    ioloop.IOLoop.current().run_sync(start_crawler)
