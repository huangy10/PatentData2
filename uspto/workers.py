# coding=utf-8
import logging

from datetime import datetime, timedelta
from tornado import gen, ioloop, httpclient, queues
from urllib import urlencode
from Patent.models import *

from parsers import DetailParser, IndexParser

# 直接使用ip可以省去极其费时的DNS时间
domain_name = "http://151.207.240.26"

index_url_template = ""

logger = logging.getLogger()


class Task(object):

    def __init__(self, req, task_type, patent, retries=0):
        self.req = req
        self.task_type = task_type
        self.patent = patent
        self.retries = retries

    def __str__(self):
        return "(%s):(%s)" % (self.task_type, self.req.url)


class Worker(object):

    @gen.coroutine
    def go(self):
        raise NotImplementedError

    def write_log_file(self, content):
        with open("log.html", "w") as f:
            f.write(content)

    def pre_process_url(self, url):
        if url.startswith("http"):
            return url
        return "%s%s" % (domain_name, url)


class IndexURLMaker(object):

    def __init__(self, countries, skip):
        self.countries = countries
        self.is_empty = False
        cache = dict()
        for c in countries:
            cache[c.code] = c
        self.country_cache = cache
        self.move_to_next_country = True

        self.page = 1
        self.country_idx = -1
        self.index_workers = []
        self.caching_us = countries[0].code == "US"
        if self.caching_us:
            self.page = 1 + skip
        super(IndexURLMaker, self).__init__()

    def make_url(self, page, country):
        param = {
            "Sect1": "PTO2",
            "Sect2": "HITOFF",
            "u": "/netahtml/PTO/search-adv.htm",
            "r": "0",
            "p": page,
            "f": "S",
            "l": "50",
            "Query": "ACN/%s AND APD/20010101->20141231" % country,
            "d": "PTXT"
        }
        url = "{domain}/netacgi/nph-Parser?{query}".format(
            domain=domain_name,
            query=urlencode(param)
        )
        return url

    def __next__(self):
        return self.next()

    def __iter__(self):
        return self

    @gen.coroutine
    def next(self):
        if self.move_to_next_country:
            if not self.caching_us:
                self.page = 1
            self.move_to_next_country = False
            self.country_idx += 1
        else:
            self.page += 1
        if self.country_idx >= len(self.countries):
            raise StopIteration()
        country = self.countries[self.country_idx].code
        if country != "US" and self.caching_us:
            logger.info(u"\n\nUS caching index tasks all dispatched, waiting detail workers to finish\n")
            tasks = []
            for w in self.index_workers:
                tasks.append(w.queue.join())
            yield tasks
            logger.info(u"\nFinish Caching US Patent\n\n")
            self.caching_us = False
        raise gen.Return((self.make_url(self.page, country), country, self.page))


class IndexWorker(Worker):

    def __init__(self, name, url_maker, session=new_session()):
        self.name = name
        self.session = session
        self.url_maker = url_maker
        super(IndexWorker, self).__init__()

        # main task queue
        self.queue = queues.Queue(maxsize=1000)
        # fetch client
        self.client = httpclient.AsyncHTTPClient()

        self.done = False

        self.us = url_maker.countries[0]

        workers = []
        for i in range(20):
            worker = DetailWorker("%s" % i, self, session)
            workers.append(worker)
        self.workers = workers

        self.url_maker.index_workers.append(self)

    @property
    def caching_us(self):
        return self.url_maker.caching_us

    @gen.coroutine
    def go(self):
        logger.info(u"爬虫 %s 启动" % self.name)
        if self.caching_us:
            logger.info(u"%s begin caching us patents" % self.name)
        for w in self.workers:
            w.go()
        while True:
            # 控制一下
            url, country, page = yield self.url_maker.next()
            if url is None:
                break
            logger.info(u"===========%s - %s" % (self.name, url))
            logger.info(u"Working on country: %s, page: %s, with queue size: %s" % (country, page, self.queue.qsize()))
            req = httpclient.HTTPRequest(url, request_timeout=1000, connect_timeout=1000)
            count = yield self.fetch_url(req)
            self.url_maker.move_to_next_country = count < 50
        self.done = True

    @gen.coroutine
    def fetch_url(self, url):
        while True:
            res = yield self.client.fetch(url, raise_error=False)
            if res.code != 200:
                logger.warning(u"===========%s - retry - %s" % (self.name, url.url))
                yield gen.sleep(10)
                continue
            parser = IndexParser(res.body, url)
            try:
                patents = parser.analyze()
            except IndexError as e:
                logger.warning(u"===========%s - retry because of IndexError - %s" % (self.name, url.url))
                logger.warning(u"===========%s: %s" % (self.name, e.message))
                yield gen.sleep(10)
                continue
            for p in patents:
                new_task = Task(
                    httpclient.HTTPRequest(self.pre_process_url(p[2]),
                                           request_timeout=1000,
                                           connect_timeout=1000),
                    "detail", None
                )
                yield self.queue.put(new_task)
            raise gen.Return(len(patents))
        self.done = True


class DetailWorker(Worker):

    def __init__(self, idx, index_worker, session=new_session()):
        self.idx = idx
        self.name = "%s-%s" % (index_worker.name, idx)
        self.queue = index_worker.queue
        self.index_worker = index_worker
        self.session = session
        self.client = index_worker.client
        super(DetailWorker, self).__init__()

    @property
    def country_cache(self):
        return self.index_worker.url_maker.country_cache

    @gen.coroutine
    def go(self):
        logger.info(u"子爬虫 %s 启动" % self.name)
        while not self.index_worker.done or self.queue.qsize() > 0:
            task = yield self.queue.get()
            if task is None:
                continue
            logger.info(u"%s %s", self.name, task)
            if task.task_type == "detail":
                yield self.get_detail(task)
            elif task.task_type == "citation":
                yield self.get_citations(task)
            self.queue.task_done()

    @gen.coroutine
    def get_detail(self, task):
        while True:
            res = yield self.client.fetch(task.req, raise_error=False)
            if res.code != 200:
                logger.warning(u"%s detail retry %s:%s" % (self.name, res.code, res.error))
                task.retries += 1
                yield gen.sleep(5)
                continue
            parser = DetailParser(res.body, task.req.url)
            if not self.index_worker.caching_us:
                try:
                    country_code = parser.get_country_code()
                except Exception as e:
                    logger.error(u"%s Error when parsing country code: %s" % (self.name, task.req.url))
                    logger.error(u"%s Error Info: %s" % e)
                    raise e
                try:
                    country = self.country_cache[country_code]
                except KeyError:
                    logger.warning(u"%s drop detail from country: %s" % (self.name, country_code))
                    break
            else:
                country = self.index_worker.us
            try:
                p_id = parser.get_patent_number()
                patent, created = self.get_or_create_patent(p_id)
                if created:
                    parser.analyze()(patent)
                    patent.country = country
            except KeyError as e:
                logger.warning(u"%s Error when parsing" % self.name)
                logger.warning(u"%s: %s" % (self.name, e.message))
                yield gen.sleep(10)
                continue
            if task.patent is not None:
                patent.cited_by.append(task.patent)
            if created:
                self.session.add(patent)
            self.session.commit()

            if self.index_worker.caching_us:
                # 开始第一轮缓存美国的专利时,不进行引用检查
                return
            link = parser.get_citation_link()
            if link is None:
                break
            link = self.pre_process_url(link)
            new_task = Task(httpclient.HTTPRequest(link, request_timeout=1000, connect_timeout=1000),
                            "citation", patent)
            yield self.queue.put(new_task)
            break

    @gen.coroutine
    def get_citations(self, task):
        try:
            while True:
                logger.info(u"%s Enter While Zone" % self.name)
                res = yield self.client.fetch(task.req, raise_error=False)
                if res.code != 200:
                    # logger.warning(u"%s citation retry %s:%s" % (self.name, res.code, res.error))
                    task.retries += 1
                    yield gen.sleep(5)
                    continue
                parser = IndexParser(res.body, task.req.url)
                try:
                    links = parser.analyze()
                except IndexError as e:
                    # logger.info(u"%s citation retry: %s" % (self.name, e.message))
                    yield gen.sleep(10)
                    continue
                if len(links) == 0:
                    # try to get single document page
                    logger.info(u"%s find single document page at %s" % (self.name, task.req.url))
                    link = parser.single_link()
                    if link is not None:
                        link = self.pre_process_url(link)
                        new_task = Task(httpclient.HTTPRequest(link, request_timeout=1000, connect_timeout=1000),
                                        "detail", task.patent)
                        yield self.queue.put(new_task)
                    break
                else:
                    logger.info(u"%s find %s citation data" % (self.name, len(links)))
                for link in links:
                    link = self.pre_process_url(link[2])
                    new_task = Task(httpclient.HTTPRequest(link, request_timeout=1000, connect_timeout=1000),
                                    "detail", task.patent)
                    yield self.queue.put(new_task)

                # try to get link of next page
                next_list = parser.get_next_page_link()
                if next_list is None:
                    break
                task.req = httpclient.HTTPRequest(
                    self.pre_process_url(next_list), request_timeout=1000, connect_timeout=1000
                )
                task.retries = 0
                logger.info(u"%s go to next citation page %s" % (self.name, next_list))
            logger.info(u"%s Leave While Zone" % self.name)
        except Exception as e:
            logger.error(u"%s citation- %s" % (self.name, e))
            logger.error(u"%s at task: %s" % (self.name, task.req.url))
            raise e

    def get_or_create_patent(self, p_id):
        session = self.session
        logger.info(u"%s begin query")
        res = session.query(Patent).filter_by(p_id=p_id).first()
        logger.info(u"%s finish query")
        if res is not None:
            return res, False
        else:
            res = Patent()
            res.p_id = p_id
            return res, True
