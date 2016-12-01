# coding=utf-8
from tornado import gen, queues, httpclient, locks, ioloop
from datetime import datetime, timedelta

from auth import login
from models import *
from parse import SearchResultParser, DetailResultParser

domain_name = "http://global.soopat.com"


class Worker(object):
    @gen.coroutine
    def go(self):
        raise NotImplementedError

    def write_log_file(self, content):
        if content is not None:
            with open("log.html", "w") as f:
                f.write(content)

    def come_to_validate_image(self, soup):
        res = soup.find("img", {"src": "/Patent/ValidateImage"}) is not None
        if res:
            print "+++++++++++++++++++WARNING+++++++++++++++++++++++"
        return res


class DetailTask(object):
    def __init__(self, country, r_url, retries=0):
        self.country = country
        self.r_url = r_url
        self.cite_by = None
        self.retries = retries
        super(DetailTask, self).__init__()


class SearchWorker(Worker):
    url_template = u"http://global.soopat.com/Patent/Result?" \
                   u"SearchWord=SQR%3A(%20{country_code}%20)%20SQRQ%3A(%20{date}%20)%20&" \
                   u"PatentIndex={index}&Sort=0&g=212"
    user_agent = u"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_12_1) AppleWebKit/537.36" \
                 u" (KHTML, like Gecko) Chrome/54.0.2840.98 Safari/537.36"

    def __init__(self, name, countries, session=new_session()):
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
        self.session = session
        self.client = httpclient.AsyncHTTPClient()
        self.search_done = False
        self.cookies_update_lock = locks.Lock()
        self.cookies_updating = False
        self.countries_cache = {}

        self.total_index = 0
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
        self.update_cookies()
        print u"%s 获取到Cookie: %s" % (self.name, self.cookies)
        print u"%s 启动子爬虫" % self.name

        for worker in self.workers:
            worker.go()

        start_date = datetime(year=2001, month=1, day=1)
        end_date = datetime(year=2014, month=12, day=31)
        day_count = (end_date - start_date).days + 1
        for country in self.countries:
            self.countries_cache[country.code] = country
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
                if res.body is not None:
                    with open("log.html", "w") as f:
                        f.write(res.body)
                print u"%s 搜索 %s: %s 时遇到错误, 错误码为 %s" % (self.name, country.code, index, res.code)
                # yield self.update_cookies()
                yield gen.sleep(5)
                continue
            parser = SearchResultParser(res.body, url)
            patents = parser.analyze()
            fetch_count = len(patents)
            index += fetch_count
            for p in patents:
                yield self.queue.put(DetailTask(country, p))
            print u"====================================================================%s" % (self.total_index + index)
            if fetch_count < 10:
                if fetch_count == 0 and not parser.reach_end():
                    raise ValueError
                break
            yield gen.sleep(3)

        self.total_index += index

    @gen.coroutine
    def update_cookies(self):
        try:
            with (yield self.cookies_update_lock.acquire(1)):
                # if self.cookies_updating:
                #     return
                if self.cookies is None:
                    try:
                        with open("cookies.txt") as f:
                            self.cookies = f.read()
                            if self.cookies is not None:
                                return
                    except IOError:
                        pass
                cookies = login()
                cookies_str = []
                for (key, val) in cookies.items():
                    cookies_str.append(u"%s=%s" % (key, val))
                cookies = ";".join(cookies_str)
                with open("cookies.txt", "w") as f:
                    f.write(cookies)
                self.cookies = cookies
        except gen.TimeoutError:
            pass


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
            print u"%s 开始爬取 %s[%s]" % (self.name, task.r_url, task.retries)
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
                task.retries += 1
                yield self.queue.put(task)
                yield gen.sleep(5)
                continue
            parser = DetailResultParser(
                content=res.body, url=url)
            p, created = self.get_or_create_patent(parser.get_url_id())
            p.country = country
            if created:
                try:
                    parser.analyze()(p)
                except AttributeError as e:
                    if self.come_to_validate_image(parser.soup):
                        yield gen.sleep(60)
                        yield self.queue.put(task)
                        continue
                    self.write_log_file(parser.soup.prettify("utf8"))
                    ioloop.IOLoop.current().stop()
                    raise e
                self.session.add(p)
            parser.debug(self.name)
            self.session.commit()

            citations = parser.cited_patents()
            if len(citations) > 0:
                print u"======%s 发现了%s条引用数据" % (self.name, len(citations))
                for url in citations:
                    # 我们来同步的将本页面下的引用的专利加进来
                    url_id = url.split("/")[-1]
                    if self.patent_exists(url_id):
                        continue
                    yield self.fetch_citation(url, patent=p)
            print u"%s 完成爬取 %s[%s]" % (self.name, task.r_url, task.retries)
            self.queue.task_done()

    @gen.coroutine
    def fetch_citation(self, url, patent, retries=0):
        yield gen.sleep(1)
        if retries > 0:
            print u"%s 获取引用数据%s, 第%s次重试" % (self.name, url, retries)
        else:
            print u'%s 获取引用数据%s' % (self.name, url)
        url = self.make_url(url)
        req = httpclient.HTTPRequest(
            url=url,
            headers={"Cookie": self.search.cookies},
            follow_redirects=False
        )
        res = yield self.client.fetch(req, raise_error=False)
        if res.code != 200:
            if res.code == 302:
                print u"%s 无法打开专利%s" % (self.name, url)
                return
            if retries >= 5:
                return
            print u"%s 获取引用数据%s失败, 睡眠五秒钟" % (self.name, url)
            yield gen.sleep(5)
            yield self.fetch_citation(url, patent, retries + 1)
            return

        parser = DetailResultParser(content=res.body, url=url)
        try:
            country_code = parser.get_country()
        except AttributeError as e:
            if self.come_to_validate_image(parser.soup):
                yield gen.sleep(60)
                yield self.fetch_citation(url, patent, retries)
                return
            self.write_log_file(parser.soup.prettify("utf8"))
            ioloop.IOLoop.current().stop()
            raise e
        if country_code not in self.search.countries_cache:
            print country_code
            return
        p, created = self.get_or_create_patent(parser.get_url_id())

        if created:
            parser.analyze()(p)

            if country_code is None:
                print u"%s 无法确认%s的作者国别" % (self.name, url)
                return
            try:
                p.country = self.search.countries_cache[country_code]
            except KeyError:
                return
            except Exception as e:
                print country_code, url
                raise e

        p.cited_patents.append(patent)
        if created:
            self.session.add(p)
        parser.debug(self.name)
        self.session.commit()

    def get_or_create_patent(self, url_id):
        session = self.session
        patent = session.query(Patent).filter_by(sqlalchemy.or_(url_id=url_id, p_id=url_id)).first()
        if patent:
            return patent, False
        else:
            return Patent(), True

    def patent_exists(self, url_id):
        session = self.session
        return session.query(Patent).filter_by(sqlalchemy.or_(url_id=url_id, p_id=url_id)).first() is not None

