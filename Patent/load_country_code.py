import os
import xlrd
from models import *


def load_country_code(session=new_session()):
    if session.query(Country).count() > 0:
        return
    path = os.path.join(os.path.abspath(os.path.dirname(__file__)), "data", "country_code.xlsx")
    book = xlrd.open_workbook(path)
    sheet = book.sheets()[0]
    for row in range(1, sheet.nrows):
        val = sheet.row_values(row)
        c = Country(name=val[0], code=val[1])
        session.add(c)
    session.commit()
