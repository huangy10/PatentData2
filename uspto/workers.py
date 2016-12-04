# coding=utf-8
from datetime import datetime, timedelta
from tornado import gen, ioloop, httpclient, queues
from urllib import urlencode
from Patent.models import *

from parsers import DetailParser, IndexParser

# 直接使用ip可以省去极其费时的DNS时间
domain_name = "http://151.207.240.26"

index_url_template = ""


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

    def __init__(self, countries):
        self.countries = countries
        self.is_empty = False
        cache = dict()
        for c in countries:
            cache[c.code] = c
        self.country_cache = cache
        self.move_to_next_country = True

        self.page = 1
        self.country_idx = -1
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

    def next(self):
        if self.move_to_next_country:
            self.page = 1
            self.move_to_next_country = False
            self.country_idx += 1
        else:
            self.page += 1
        if self.country_idx >= len(self.countries):
            raise StopIteration()
        return self.make_url(self.page, self.countries[self.country_idx].code)


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

        workers = []
        for i in range(20):
            worker = DetailWorker("%s" % i, self, session)
            workers.append(worker)
        self.workers = workers

    @gen.coroutine
    def go(self):
        print u"爬虫 %s 启动" % self.name
        for w in self.workers:
            w.go()
        while True:
            # 控制一下
            url = self.url_maker.next()
            if url is None:
                break
            print u"===========%s - %s" % (self.name, url)
            req = httpclient.HTTPRequest(url, request_timeout=1000, connect_timeout=1000)
            count = yield self.fetch_url(req)
            self.url_maker.move_to_next_country = count < 50
        self.done = True

    @gen.coroutine
    def fetch_url(self, url):
        while True:
            res = yield self.client.fetch(url, raise_error=False)
            if res.code != 200:
                print u"===========%s - retry - %s" % (self.name, url.url)
                yield gen.sleep(10)
                continue
            parser = IndexParser(res.body, url)
            patents = parser.analyze()
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
        print u"子爬虫 %s 启动" % self.name
        while not self.index_worker.done or self.queue.qsize() > 0:
            task = yield self.queue.get()
            if task is None:
                continue
            print self.name, task
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
                print u"%s detail retry %s:%s" % (self.name, res.code, res.error)
                task.retries += 1
                yield gen.sleep(5)
                continue
            parser = DetailParser(res.body, task.req.url)
            country_code = parser.get_country_code()
            try:
                country = self.country_cache[country_code]
            except KeyError:
                print u"%s drop detail from country: %s" % (self.name, country_code)
                break
            p_id = parser.get_patent_number()
            patent, created = self.get_or_create_patent(p_id)
            parser.analyze()(patent)
            patent.country = country
            if task.patent is not None:
                patent.cited_by.append(task.patent)
            if created:
                self.session.add(patent)
            self.session.commit()

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
        while True:
            res = yield self.client.fetch(task.req, raise_error=False)
            if res.code != 200:
                print u"%s citation retry %s:%s" % (self.name, res.code, res.error)
                task.retries += 1
                yield gen.sleep(5)
                continue
            parser = IndexParser(res.body, task.req.url)
            links = parser.analyze()
            if len(links) == 0:
                # try to get single document page
                link = parser.single_link()
                if link is not None:
                    link = self.pre_process_url(link)
                    new_task = Task(httpclient.HTTPRequest(link, request_timeout=1000, connect_timeout=1000),
                                    "detail", task.patent)
                    yield self.queue.put(new_task)
                break
            else:
                print u"%s find %s citation data" % (self.name, len(links))
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
            print u"%s go to next citation page" % self.name

    def get_or_create_patent(self, p_id):
        session = self.session
        res = session.query(Patent).filter_by(p_id=p_id).first()
        if res is not None:
            return res, False
        else:
            res = Patent()
            res.p_id = p_id
            return res, True
