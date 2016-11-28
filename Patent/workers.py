# coding=utf-8
from tornado import gen, queues, httpclient

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

    url_template = "http://global.soopat.com/Patent/Result?" \
                   "SearchWord=SQR%3A(%20{country_code}%20)%20SQRQ%3A(%5B%2020010101%20TO%2020141231%5D)%20&" \
                   "PatentIndex={index}&Sort=0&g=234"
    user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36" \
                 " (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36"

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
        workers = []
        for i in range(10):
            workers.append(DetailWorker(self, i, self.session))

    def make_url(self, country_code, index):
        return self.url_template.format(
            country_code=country_code,
            index=index
        )

    @gen.coroutine
    def go(self):
        print "%s 爬虫启动" % self.name
        cookies = login()
        cookies_str = []
        for (key, val) in cookies.items():
            cookies_str.append("%s=%s" % (key, val))
        self.cookies = ";".join(cookies_str)
        print self.cookies
        for country in self.countries:
            yield self.search_country(country)

        yield self.queue.join()

    @gen.coroutine
    def search_country(self, country):
        print "开始搜索 %s" % country
        index = 0
        while True:
            url = self.make_url(country, index)
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
                print "搜索 %s: %s 时遇到错误, 错误码为 %s" % (country, index, res.code)
                yield gen.sleep(5)
                continue
            parser = SearchResultParser(res.body, url)
            patents = parser.analyze()
            index += len(patents)
            for p in patents:
                print p
            print "===============================%s" % index


class DetailWorker(Worker):

    def __init__(self, search, i, session):
        self.search = search
        self.id = i
        self.search_done = False
        self.client = httpclient.AsyncHTTPClient()
        self.session=session
        super(DetailWorker, self).__init__()

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
        return domain_name + relative_url

    @gen.coroutine
    def go(self):
        while not self.search_done or self.queue.qsize() > 0:
            # 获取下一个需要爬取的专利详情
            task = yield self.queue.get()
            country = task.country
            url = self.make_url(task.r_url)

            req = httpclient.HTTPRequest(
                url=url,
                headers={'Cookie': self.search.cookies},
                follow_redirects=False
            )
            res = yield self.client.fetch(req, raise_error=False)
            if res.code != 200:
                # 如果失败了重新加入队列,并且将这个worker睡眠五秒钟
                yield self.queue.put(task)
                yield gen.sleep(5)
                continue
            parser = DetailResultParser(
                content=res.body, url=url)
            builder = parser.analyze()
            p = builder(Patent())
            p.country = country

            citations = parser.cited_patents()
            for url in citations:
                # 我们来同步的将本页面下的引用的专利加进来
                self.fetch_citation(url, patent=p)

    def fetch_citation(self, url, patent, retries=0):
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



