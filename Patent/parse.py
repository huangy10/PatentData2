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

    def reach_end(self):
        res = self.soup.find("div", {"class": "ErrorBlock"})
        if res is not None:
            return True
        else:
            return False


class DetailResultParser(WebpageParser):

    apply_year_pattern = re.compile(r"(\d{4})-\d\d-\d\d")

    def debug(self, name):
        # print "%s~~~~~~~" % name
        # print self.get_apply_year()
        # print self.get_p_id()
        # print "~~~~~~~"
        pass

    def analyze(self):

        def patent_builder(patent):
            patent.name = self.get_patent_name()
            # patent.abstract = self.get_patent_abstract()
            patent.p_id = self.get_p_id()
            patent.apply_year = self.get_apply_year()
            patent.url_id = self.get_url_id()
        return patent_builder

    def cited_patents(self):
        tables = self.soup.find_all("table", {"id": "PatentContentTable"})
        for table in tables:
            if u"所引用" in table.previous_sibling.previous_sibling.span.string:
                links = table.find_all("a")
                return map(lambda x: x.attrs["href"], links)
        return []

    def get_country(self):
        detail_container = self.soup.find("div", {"class": "detailinfo"})
        links = detail_container.find_all("a")
        pattern = re.compile(r"\[(\w\w)\]")
        for link in links:
            content = link.string
            if content is None:
                continue
            code = re.search(pattern, content)
            if code is not None and len(code.groups()) > 0:
                return code.groups()[0]
        else:
            return None

    def get_patent_name(self):
        return self.soup.find("span", {"class": "detailtitle"}).h1.string

    def get_patent_abstract(self):
        return self.soup.find("span", {"id": "abs_"}).string[0:250]

    def get_p_id(self):
        return self.soup.find("table", {"id": "PatentContentTable"})\
            .find_all("td", {"class": "r"})[1].string.strip()

    def get_url_id(self):
        return self.url.split("/")[-1]

    def get_apply_year(self):
        apply_info = self.soup.find("span", {"class": "detailtitle"}).strong.i.string
        return int(re.search(self.apply_year_pattern, apply_info).groups()[0])
