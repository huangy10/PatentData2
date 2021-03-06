import re
from Patent.parse import WebpageParser, BeautifulSoup


class IndexParser(WebpageParser):

    def analyze(self):
        try:
            items = self.soup.find_all("table")[1].find_all("tr")
        except IndexError:
            return []
        res = []
        for item in items:
            links = item.find_all("a")
            if len(links) < 2:
                continue
            no = links[0].get_text()
            title = links[1].string
            link = links[0]["href"]
            res.append((no, title, link))
        return res

    def single_link(self):
        title = self.soup.title
        if title.get_text() != "Single Document":
            return None
        meta = self.soup.meta
        if meta is None:
            return meta
        return meta["content"].replace("1;URL=", "")

    def get_next_page_link(self):
        btn = self.soup.find("img", alt="[NEXT_LIST]")
        if btn is None:
            return None
        else:
            return btn.parent["href"]


class DetailParser(WebpageParser):

    def __init__(self, content, url):
        super(DetailParser, self).__init__(content, url)
        self.country_code_patterns = [re.compile(r", \s?(\w\w)\)"), re.compile(r"\((\w\w)\)")]
        self.states = []

    def analyze(self):

        def builder(patent):
            patent.apply_year = self.get_apply_year()
            patent.p_id = self.get_patent_number()
            if patent.name is None:
                patent.name = self.get_name()

        return builder

    def get_country_code(self):
        header = self.soup.find("th", string=re.compile(r"Applicant:\s*"))
        if header is None:
            header = self.soup.find("th", string=re.compile(r"Assignee:\s*"))
            if header is None:
                return None
            data = header.parent
            for pattern in self.country_code_patterns:
                result = re.search(pattern, data.get_text())
                if result is None:
                    continue
                result = result.groups()
                if len(result) > 0:
                    return result[0]
            return None
        else:
            sub_table = header.find_next_sibling("td").find("table")
            rows = sub_table.find_all("tr")
            if len(rows) < 2:
                return None
            data_row = rows[1]
            country_code = data_row.find_all("td")[3].get_text().strip().split("\n")[0]
            return country_code

    def get_apply_year(self):
        header = self.soup.find("th", string=re.compile(r"^Filed:\s*"))
        data = header.find_next_sibling("td")
        return int(data.get_text().split(",")[-1].strip())

    def get_name(self):
        return self.soup.find("font", size="+1").get_text()

    def get_citation_link(self):
        a = self.soup.find("a", string="[Referenced By]")
        if a is None:
            return None
        return a["href"]

    def get_patent_number(self):
        tables = self.soup.find_all("table")
        if len(tables) < 3:
            return None
        table = tables[2]
        return table.find_all("td")[1].get_text().strip()


