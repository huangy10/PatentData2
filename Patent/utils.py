from .models import *
from sqlalchemy.sql import exists

def load_countries(session=new_session()):
    pass


def clear_all_countries(session=new_session()):
    session.query(Country).delete()


def patent_exist_with_p_id(patent_id, session=new_session()):
    return session.query(exists().where(Patent.p_id == patent_id)).scalar()


def patent_exist_with_url_id(url_id, session=new_session()):
    return session.query(exists().where(Patent.url_id == url_id)).scalar()
