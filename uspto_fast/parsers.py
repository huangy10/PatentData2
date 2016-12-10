import re
from uspto.parsers import DetailParser


class FullDetailParser(DetailParser):

    def get_country_full(self):
        header = self.soup.find("th", string=re.compile(r"Assignee:\s*"))
        data = header.parent
        return data.get_text()
