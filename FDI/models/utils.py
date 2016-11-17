from models import new_session
from models import Country, FDI


def clear_all_countries():
    session = new_session()
    session.query(Country).delete()
    session.commit()


def country_for_name(name):
    session = new_session()
    return session.query(Country).filter(Country.name == name).first()


def get_or_create(session, model, commit=False, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    else:
        instance = model(**kwargs)
        session.add(instance)
        if commit:
            session.commit()
        return instance, True
