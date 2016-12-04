import os
import sys

proj_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.extend([proj_dir])
print proj_dir

from tornado import ioloop, gen

from Patent.load_country_code import load_country_code
from Patent.models import *
from workers import IndexWorker, IndexURLMaker

@gen.coroutine
def start_crawler():
    load_country_code()
    session = new_session()
    countries = session.query(Country).all()
    url_maker = IndexURLMaker(countries=countries)
    futures = []
    for i in range(1):
        worker = IndexWorker(name="default-%s" % i, url_maker=url_maker, session=session)
        futures.append(worker.go())
    # yield gen.sleep(10000)
    yield futures


if __name__ == "__main__":
    ioloop.IOLoop.current().run_sync(start_crawler)
