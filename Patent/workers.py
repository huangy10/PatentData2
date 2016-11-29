# coding=utf-8
from tornado import gen, queues, httpclient
from datetime import datetime, timedelta

from auth import login
from models import *
from parse import SearchResultParser, DetailResultParser

domain_name = "http://global.soopat.com"


class Worker(object):
    @gen.coroutine
    def go(self):
        raise NotImplementedError


class DetailTask(object):
    def __init__(self, country, r_url):
        self.country = country
        self.r_url = r_url
        self.cite_by = None
        super(DetailTask, self).__init__()


class SearchWorker(Worker):
    url_template = u"http://global.soopat.com/Patent/Result?" \
                   u"SearchWord=SQR%3A(%20{country_code}%20)%20SQRQ%3A(%20{date}%20)%20&" \
                   u"PatentIndex={index}&Sort=0&g=212"
    user_agent = u"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36" \
                 u" (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36"

    def __init__(self, name, countries):
        """
        创建一个search worker
        :param name: worker的名称
        :param countries: search_worker需要搜索的国家,接受一个列表
        """
        super(SearchWorker, self).__init__()
        self.name = name
        self.queue = queues.Queue()
        self.countries = countries
        self.current_searching_countries = []
        self.skip = 0
        self.cookies = None
        self.session = new_session()
        self.client = httpclient.AsyncHTTPClient()
        self.search_done = False
        workers = []
        # 平均下来一个页面中会返回10个详情,我们创建10个detail worker能够保持队列大概持平
        for i in range(10):
            workers.append(DetailWorker(self, i, self.session))
        self.workers = workers

    def make_url(self, country_code, index, date):
        return self.url_template.format(
            country_code=country_code,
            index=index,
            date=date
        )

    @gen.coroutine
    def go(self):
        print u"%s 爬虫启动" % self.name
        print u"%s 开始登录到soopat引擎" % self.name
        cookies = login()
        cookies_str = []
        for (key, val) in cookies.items():
            cookies_str.append(u"%s=%s" % (key, val))
        self.cookies = ";".join(cookies_str)
        print u"%s 获取到Cookie: %s" % (self.name, self.cookies)
        print u"%s 启动子爬虫" % self.name

        for worker in self.workers:
            worker.go()

        start_date = datetime(year=2001, month=1, day=1)
        end_date = datetime(year=2014, month=12, day=31)
        day_count = (end_date - start_date).days + 1
        for country in self.countries:
            for single_day in [d for d in (start_date + timedelta(n) for n in range(day_count)) if d <= end_date]:
                yield self.search_country(country, single_day.strftime("%Y%m%d"))

        self.search_done = True
        yield self.queue.join()

    @gen.coroutine
    def search_country(self, country, date):
        print u"%s 开始搜索 %s" % (self.name, country.code)
        index = 0
        while True:
            url = self.make_url(country.code, index, date)
            req = httpclient.HTTPRequest(
                url=url,
                headers={"Cookie": self.cookies},
                user_agent=self.user_agent,
                follow_redirects=False
            )
            res = yield self.client.fetch(req, raise_error=False)
            if res.code != 200:
                print url
                with open("log.html", "w") as f:
                    f.write(res.body)
                print u"%s 搜索 %s: %s 时遇到错误, 错误码为 %s" % (self.name, country.code, index, res.code)
                yield gen.sleep(5)
                continue
            parser = SearchResultParser(res.body, url)
            patents = parser.analyze()
            index += len(patents)
            for p in patents:
                yield self.queue.put(DetailTask(country, p))
            print u"===============================%s" % index

            yield gen.sleep(5)


class DetailWorker(Worker):
    def __init__(self, search, i, session):
        self.search = search
        self.id = i
        self.client = httpclient.AsyncHTTPClient()
        self.session = session
        super(DetailWorker, self).__init__()

    @property
    def search_done(self):
        return self.search.search_done

    @property
    def name(self):
        return "{search}_{i}".format(
            search=self.search.name,
            i=self.id
        )

    @property
    def queue(self):
        return self.search.queue

    def make_url(self, relative_url):
        if relative_url.startswith("http"):
            return relative_url
        return domain_name + relative_url

    @gen.coroutine
    def go(self):
        print u"子爬虫 %s 启动" % self.name
        while not self.search_done or self.queue.qsize() > 0:
            # 获取下一个需要爬取的专利详情
            task = yield self.queue.get()
            if task is None:
                continue
            print u"%s 开始爬取 %s" % (self.name, task.r_url)
            country = task.country
            url = self.make_url(task.r_url)

            req = httpclient.HTTPRequest(
                url=url,
                headers={'Cookie': self.search.cookies},
                follow_redirects=False
            )
            res = yield self.client.fetch(req, raise_error=False)
            if res.code != 200:
                print u"%s 获取 %s 失败, 错误码为 %s" % (self.name, task.r_url, res.code)
                # 如果失败了重新加入队列,并且将这个worker睡眠五秒钟
                yield self.queue.put(task)
                yield gen.sleep(5)
                continue
            parser = DetailResultParser(
                content=res.body, url=url)
            builder = parser.analyze()
            p, created = self.get_or_create_patent(url.split("/")[-1])
            builder(p)
            p.country = country
            parser.debug()
            if created:
                self.session.add(p)

            citations = parser.cited_patents()
            print u"%s 发现了引用数据" % self.name
            for url in citations:
                # 我们来同步的将本页面下的引用的专利加进来
                # self.fetch_citation(url, patent=p)
                print url
            print u"======"

            self.queue.task_done()

    def fetch_citation(self, url, patent, retries=0):
        if retries > 0:
            print u"%s 获取引用数据, 第%s次重试" % (self.name, retries)
        else:
            print u'%s 获取引用数据' % self.name
        url = self.make_url(url)
        req = httpclient.HTTPRequest(
            url=url,
            headers={"Cookies": self.search.cookies},
            follow_redirects=False
        )
        res = yield self.client.fetch(req, raise_error=False)
        if res.code != 200:
            if retries >= 5:
                return
            yield gen.sleep(5)
            yield self.fetch_citation(url, patent, retries + 1)
            return
        parser = DetailResultParser(content=res.body, url=url)
        p = parser.analyze()(Patent())
        p.country = parser.get_country()

        patent.cited_patents.append(p)

        if not self.check_patent_exists(p):
            self.session.add(p)

    def check_patent_exists(self, patent):
        session = self.session
        if session.query(Patent).filter_by(p_id=patent.p_id).first() is not None:
            return False
        else:
            return True

    def get_or_create_patent(self, url_id):
        session = self.session
        patent = session.query(Patent).filter_by(url_id=url_id).first()
        if patent:
            return patent, False
        else:
            return Patent(), True
