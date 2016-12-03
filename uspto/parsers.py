import re
from Patent.parse import WebpageParser


class IndexParser(WebpageParser):

    def analyze(self):
        try:
            items = self.soup.find_all("table")[1].find_all("tr")
        except IndexError:
            return []
        res = []
        for item in items:
            links = item.find_all("a")
            if len(links) == 0:
                continue
            no = links[0].get_text()
            title = links[1].string
            link = links[0]["href"]
            res.append((no, title, link))
        return res


class DetailParser(WebpageParser):

    def __init__(self, content, url):
        super(DetailParser, self).__init__(content, url)
        self.country_code_pattern = re.compile(r", (\w\w)\)")

    def analyze(self):

        def builder(patent):
            patent.apply_year = self.get_apply_year()
            if patent.name is None:
                patent.name = self.get_name()

        return builder

    def get_country_code(self):
        header = self.soup.find("th", string=re.compile(r"Inventors:\s*"))
        data = header.find_next_sibling("td")
        result = re.search(self.country_code_pattern, data.get_text()).groups()
        if len(result) > 0:
            return result[0]
        else:
            return None

    def get_apply_year(self):
        header = self.soup.find("th", string=re.compile(r"^Filed:\s*"))
        data = header.find_next_sibling("td")
        return int(data.get_text().split(",")[-1].strip())

    def get_name(self):
        return self.soup.find("font", size="+1").get_text()

    def get_citation_link(self):
        return self.soup.find("a", string="[Referenced By]")["href"]

    def get_patent_number(self):
        table = self.soup.find("table")[2]
        return table.find_all("td")[1].get_text().strip()


