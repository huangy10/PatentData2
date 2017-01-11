import logging
import traceback

from datetime import datetime
from urllib import urlencode
from tornado import httpclient, gen, queues

from uspto.workers import Task, Worker, DetailWorker
from uspto.workers import domain_name
from uspto.parsers import IndexParser

from parsers import FullDetailParser
from models import *


logger = logging.getLogger()


def make_req(url):
    if not url.startswith("http"):
        url = domain_name + url
    return httpclient.HTTPRequest(url, request_timeout=1000, connect_timeout=1000)


class FullIndexURLMaker(object):

    def __init__(self, year, skip=0):
        self.year = year
        self.is_empty = False
        self.move_to_next_year = False
        self.page = 1 + skip
        self.workers = []

    def make_url(self, page, year):
        param = {
            "Sect1": "PTO2",
            "Sect2": "HITOFF",
            "u": "/netahtml/PTO/search-adv.htm",
            "r": "0",
            "p": page,
            "f": "S",
            "l": "50",
            "Query": "APD/{year}0101->{year}1231".format(year=year),
            "d": "PTXT"
        }
        url = "{domain}/netacgi/nph-Parser?{query}".format(
            domain=domain_name,
            query=urlencode(param)
        )
        return url

    def next(self):
        if self.move_to_next_year:
            self.is_empty = True
            return None, self.page, self.year
        else:
            self.page += 1
        # if self.year > 2014:
        #     logger.info(u"\n\nFinish Task Dispatch, Waiting for remaining tasks in queue\n\n")
        #     return None, self.page, self.year
        return self.make_url(self.page, self.year), self.page, self.year


class FullIndexWorker(Worker):

    def __init__(self, name, url_maker, session=new_session()):
        self.name = name
        self.url_maker = url_maker
        self.session = session
        super(FullIndexWorker, self).__init__()

        self.queue = queues.Queue()
        self.client = httpclient.AsyncHTTPClient()
        workers = []
        for i in range(10):
            worker = FullDetailWorker("%s" % i, self, session)
            workers.append(worker)
        self.workers = workers

        self.url_maker.workers.append(self)
        self.done = False

        self.page = 0
        self.year = 2000

    @gen.coroutine
    def go(self):
        logger.info(u"Crawler %s Starts!" % self.name)
        for w in self.workers:
            w.go()

        while True:
            url, page, year = self.url_maker.next()
            if url is None:
                break
            logger.info(u"==========%s - %s" % (self.name, url))
            logger.info(u"Working on page: %s year: %s, with queue size: %s" % (page, year, self.queue.qsize()))
            self.page = page
            self.year = year
            req = make_req(url)
            while True:
                count, is_last_page = yield self.fetch_search_result(req)
                if not is_last_page and count == 0:
                    logger.warning(u"Index Warning: meet invalid index page at %s" % req.url)
                    continue
                self.url_maker.move_to_next_year = is_last_page
                break

        self.done = True
        yield self.queue.join()


    @gen.coroutine
    def fetch_search_result(self, req):
        while True:
            res = yield self.client.fetch(req, raise_error=False)
            if res.code != 200:
                logger.warning(u"==========%s retry %s" % (self.name, req.url))
                yield gen.sleep(10)
                continue
            parser = IndexParser(res.body, req.url)
            try:
                patents = parser.analyze()
            except IndexError as e:
                logger.warning(u"===========%s - retry because of IndexError - %s" % (self.name, req.url))
                logger.warning(u"===========%s: %s" % (self.name, e.message))
                yield gen.sleep(10)
                continue

            for p in patents:
                new_task = Task(make_req(p[2]), "detail", None)
                while self.queue.qsize() > 100:
                    logger.info(u"===========%s: queue too long, wait for 1 min" % self.name)
                    logger.info(u"Working on page: %s year: %s, with queue size: %s"
                        % (self.page, self.year, self.queue.qsize()))
                    yield gen.sleep(60)
                yield self.queue.put(new_task)

            raise gen.Return((len(patents), parser.is_last_page()))


class FullDetailWorker(DetailWorker):

    @property
    def country_cache(self):
        raise NotImplemented

    @gen.coroutine
    def get_detail(self, task):
        try:
            while True:
                logger.info(u"%s Enter While Zone" % self.name)
                res = yield self.client.fetch(task.req, raise_error=False)
                if res.code != 200:
                    logger.warning(u"%s detail retry %s:%s" % (self.name, res.code, res.error))
                    task.retries += 1
                    yield gen.sleep(5)
                    continue
                logger.info(u"%s response got" % self.name)
                parser = FullDetailParser(res.body, task.req.url)
                try:
                    p_id = parser.get_patent_number()
                    if p_id is None:
                        logger.warning(u"%s PID None, retry!" % self.name)
                        yield gen.sleep(5)
                        continue
                    patent, created = self.get_or_create_patent(p_id)
                    if created:
                        parser.analyze()(patent)
                        patent.assignee = parser.get_country_full()
                        patent.country_code = parser.get_country_code()
                        patent.reference_link = parser.get_citation_link()
                        if patent.country_code is None:
                            logger.warning(u"%s cant find country code" % self.name)
                except KeyError as e:
                    self.session.rollback()
                    logger.warning(u"%s Error when parsing" % self.name)
                    logger.warning(u"%s: %s" % (self.name, e.message))
                    yield gen.sleep(5)
                    continue
                    # raise e
                if task.patent is not None:
                    patent.cited_by.append(task.patent)
                if created:
                    self.session.add(patent)
                self.session.commit()
                # if task.patent is not None:
                #     break
                # link = parser.get_citation_link()
                # if link is None:
                #     break
                # new_task = Task(make_req(link),
                #                 "citation", patent)
                # yield self.queue.put(new_task)
                # break
                break
            logger.info(u"%s Leave While Zone" % self.name)
        except Exception as e:
            logger.error(u"%s detail- %s" % (self.name, traceback.print_exc()))
            logger.error(u"%s error info: %s" % (self.name, e))
            logger.error(u"%s at task: %s" % (self.name, task.req.url))
            # raise e
            yield self.queue.put(task)

    def get_or_create_patent(self, p_id):
        session = self.session
        res = session.query(Patent).filter_by(p_id=p_id).first()
        if res is not None:
            return res, False
        else:
            res = Patent()
            res.p_id = p_id
            return res, True
