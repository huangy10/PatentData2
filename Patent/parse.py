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
        res = self.soup

        def patent_builder(patent):
            pass

        return patent_builder
