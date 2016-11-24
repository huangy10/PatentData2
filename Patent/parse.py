# coding=utf-8
import re
from bs4 import BeautifulSoup


class WebpageParser(object):

    def __init__(self, content, url):
        self.content = content
        self.url = url
        self.soup = BeautifulSoup(content, "html.parser")
        super(WebpageParser, self).__init__()

    def analyze(self):
        raise NotImplementedError


class SearchResultParser(WebpageParser):

    def analyze(self):
        """
        分析内容并返回分析结果
        :return:
        """
        res = self.soup.find_all("a", {"id": re.compile("^english.*")})
        if res is None:
            return None
        return map(lambda x: x.attrs["href"], res)


class DetailResultParser(WebpageParser):

    def analyze(self):

        def patent_builder(patent):
            patent.name = self.soup.find("span", {"class": "detailtitle"}).h1.string
            patent.abstract = self.soup.find("span", {"id": "abs_"}).string[0:250]
            patent.p_id = self.soup.find("table", {"id": "PatentContentTable"})\
                .find_all("td", {"class": "r"})[1].string.strip()

        return patent_builder

    def cited_patents(self):
        table = self.soup.find_all("table", {"id": "PatentContentTable"})[1]
        links = table.find_all("a")
        return map(lambda x: x.attrs["href"], links)
