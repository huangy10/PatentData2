# coding=utf-8
import sys
import xlwt
import xlrd

from models.utils import get_or_create
from models.models import *

country_names_without_coma = [c for (c, ) in new_session().query(Country.name).all()]


def load_countries(dir_path, save_to_db=True):
    file_names = os.listdir(dir_path)
    country_names = [f.replace(".xls", "").replace(",", "").decode("utf8")
        for f in file_names if (f.endswith(".xls") or f.endswith(".xlsx"))]
    if save_to_db:
        session = new_session()
        new_country_num = 0
        for name in country_names:
            _, created = get_or_create(session, Country, commit=False, name=name)
            if created:
                new_country_num += 1
        session.commit()
        return new_country_num
    global country_names_without_coma
    country_names_without_coma = [c for (c, ) in new_session().query(Country.name).all()]
    return country_names


def mark_g20_countries(dir_path):
    file_names = os.listdir(dir_path)
    # county_names = [f.split(".")[0].decode("utf8") for f in file_names if (f.endswith(".xls") or f.endswith(".xlsx"))]
    country_names = [f.replace(".xls", "").replace(",", "").decode("utf8")
                     for f in file_names if (f.endswith(".xls") or f.endswith(".xlsx"))]
    session = new_session()
    session.query(Country).filter(Country.name.in_(country_names))\
        .update({Country.is_g20: True}, synchronize_session=False)
    session.commit()


def export_fast(session=new_session()):
    col_countries = session.query(Country).filter_by(is_g20=True).all()
    row_countries = session.query(Country).all()
    book = xlwt.Workbook()
    task_num = session.query(FDI).count()
    task_done = 0
    printProgress(task_done, task_num, prefix='Loading Records In to Mem:', suffix='Complete', barLength=50)

    cache = dict()
    for r in session.query(FDI):
        k = make_key_for(r.from_c, r.to_c, r.year)
        v = cache.get(k, None)
        if v is None:
            cache[k] = max(r.value, 0)
        else:
            cache[k] = (max(v, 0) + max(r.value, 0)) / 2

        task_done += 1
        printProgress(task_done, task_num, prefix='Loading Records In to Mem:', suffix='Complete', barLength=50)

    task_num = 12 * (len(col_countries) + 1) * (len(row_countries) + 1)
    task_done = 0
    printProgress(task_done, task_num, prefix='Writing:', suffix='Complete', barLength=50)
    for year in range(2001, 2013):
        sheet = book.add_sheet(u"%s" % year, cell_overwrite_ok=True)

        for row, row_c in enumerate(row_countries):
            sheet.write(row + 1, 0, row_c.name)
            for col, col_c in enumerate(col_countries):
                if row == 0:
                    sheet.write(0, col + 1, col_c.name)
                else:
                    sheet.write(row + 1, col + 1, cache.get(make_key_for(row_c, col_c, year), 0))

                task_done += 1
                printProgress(task_done, task_num, prefix='Progress:', suffix='Complete', barLength=50)
    book.save("output/output_fast.xls")


def make_key_for(row_c, col_c, year):
    return u"%s-%s-%s" % (row_c.name, col_c.name, year)


def export(session=None):
    session = session or new_session()
    col_countries = session.query(Country).filter_by(is_g20=True).all()
    row_countries = session.query(Country).all()

    book = xlwt.Workbook()
    task_num = 12 * (len(col_countries) + 1) * (len(row_countries) + 1)
    task_done = 0
    printProgress(task_done, task_num, prefix='Progress:', suffix='Complete', barLength=50)
    for year in range(2001, 2013):
        sheet = book.add_sheet(u"%s" % year, cell_overwrite_ok=True)

        for row, row_c in enumerate(row_countries):
            sheet.write(row + 1, 0, row_c.name)
            for col, col_c in enumerate(col_countries):
                if row == 0:
                    sheet.write(0, col + 1, col_c.name)
                else:
                    sheet.write(row + 1, col + 1, calc_fdi_in(row_c, col_c, year, session))

                task_done += 1
                printProgress(task_done, task_num, prefix='Progress:', suffix='Complete', barLength=50)

    printProgress(task_num, task_num, prefix='Loading Records In to Mem:', suffix='Complete', barLength=50)
    book.save("output/output.xls")


def calc_fdi_in(row_c, col_c, year, session=new_session()):
    res = session.query(FDI).filter_by(from_c=row_c, to_c=col_c, year=year).all()
    if len(res) == 0:
        return 0
    return reduce(lambda x, y: x + max(y.value, 0), res, 0) / float(len(res))


def clear_all_fdi_record(session=None):
    session = session or new_session()
    session.query(FDI).delete()
    session.commit()


def load_fdi_record(dir_path, session=None):
    session = session or new_session()
    clear_all_fdi_record(session)

    file_names = os.listdir(dir_path)
    country_names = [f.replace(".xls", "")
                     for f in file_names if (f.endswith(".xls") or f.endswith(".xlsx"))]

    for country in country_names:
        print country
        load_fdi_record_for_country(country, dir_path, session)


def load_fdi_record_for_country(country, base_dir, session=None):
    session = session or new_session()

    if isinstance(base_dir, str):
        base_dir = base_dir.decode("utf8")
    x = u"{country}.xls".format(country=country.decode("utf8"))
    filename = os.path.join(base_dir, x)

    country = session.query(Country).filter_by(name=country.replace(",", "").decode("utf8")).one()
    book = xlrd.open_workbook(filename)

    def sheet_analysis(sheet, idx):
        year_row, year_col = find_year_start_pos(sheet)
        # country_col = 0
        # start_row = year_row
        #
        # find_country = False
        # for row in range(year_row + 1, sheet.nrows):
        #     for col in range(0, year_col):
        #         val = sheet.cell(row, col).value.strip()
        #         if len(val) == 0:
        #             continue
        #         elif val in country_names_without_coma:
        #             country_col = col
        #             start_row = row
        #             find_country = True
        #             break
        #
        #     if find_country:
        #         break
        #
        # if not find_country:
        #     print "error", country
        #     return

        for row in range(year_row + 1, sheet.nrows):
            country_name = None
            for col in range(0, year_col):
                name = sheet.row_values(row)[col]
                if name in country_names_without_coma:
                    country_name = name
                    break
            if country_name is None:
                continue

            with session.no_autoflush:
                country2 = session.query(Country).filter_by(name=country_name).one()

            for y, col in enumerate(range(year_col, sheet.ncols)):
                val = sheet.row_values(row)[col]
                if not isinstance(val, float):
                    val = float(0)

                if (country.name == "Japan" and country2.name == "China") or \
                        (country2.name == "Japan" and country.name == "China"):
                    print val, idx

                if idx == 0:
                    fdi = FDI(from_c=country2, to_c=country, year=2001 + y, value=val, data_type=u"in")
                elif idx == 1:
                    fdi = FDI(from_c=country, to_c=country2, year=2001 + y, value=val, data_type=u"out")
                else:
                    continue
                session.add(fdi)

        session.commit()

    sheet_analysis(book.sheets()[0], 0)
    sheet_analysis(book.sheets()[1], 1)


def find_year_start_pos(sheet):
    nrow = sheet.nrows
    for row in range(nrow):
        for col, val in enumerate(sheet.row_values(row)):
            if isinstance(val, float) and int(val) == 2001:
                return row, col


def printProgress (iteration, total, prefix = '', suffix = '', decimals = 1, barLength = 100):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        barLength   - Optional  : character length of bar (Int)
    """
    formatStr = "{0:." + str(decimals) + "f}"
    percent = formatStr.format(100 * (iteration / float(total)))
    filledLength = int(round(barLength * iteration / float(total)))
    bar = '█' * filledLength + '-' * (barLength - filledLength)
    sys.stdout.write('\r%s |%s| %s%s %s' % (prefix, bar, percent, '%', suffix)),
    if iteration == total:
        sys.stdout.write('\n')
    sys.stdout.flush()
