import os
import xlrd

from models.utils import get_or_create
from models import models


def load_countries(dir_path, save_to_db=True):
    file_names = os.listdir(dir_path)
    county_names = [f.split(".")[0].decode("utf8") for f in file_names if (f.endswith(".xls") or f.endswith(".xlsx"))]
    if save_to_db:
        session = models.new_session()
        new_country_num = 0
        for name in county_names:
            _, created = get_or_create(session, models.Country, commit=False, name=name)
            if created:
                new_country_num += 1
        session.commit()
        return new_country_num
    return county_names
