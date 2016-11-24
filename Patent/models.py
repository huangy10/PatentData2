# coding=utf-8
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Boolean
from sqlalchemy import Table
from sqlalchemy.ext.declarative import as_declarative, declared_attr
import sqlalchemy.orm

engine = create_engine('sqlite:///{path}/db.sqlite3'.format(path=os.path.dirname(__file__)),
    encoding='utf8', echo=True)


@as_declarative()
class Base(object):
    id = Column(Integer, primary_key=True, autoincrement=True)

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower()


cite = Table(
    "citation", Base.metadata,
    Column("patent_id", Integer, ForeignKey("patent.id")),
    Column("country_id", Integer, ForeignKey("country.id"))
)


class Country(Base):

    name = Column(String(50), nullable=False)
    code = Column(String(10), nullable=False)
    flag = Column(Boolean, default=False)


class Patent(Base):
    # 专利名称
    name = Column(String(250))

    # 申请年份
    apply_year = Column(Integer, default=2000)

    # 专利id
    p_id = Column(String(100), unique=True)
    apply_id = Column(String(100), unique=True)

    # url id
    url_id = Column(String(100), unique=True)

    # 摘要
    abstract = Column(String(250))

    # 类别
    category = Column(String(20))

    # 申请人,暂时不用
    applier = Column(String(250))
    # FM: 发明, SY: 实用, WG: 外观
    type = Column(String(5))
    # valid, applying, invalid
    status = Column(String(10))

    country_id = Column(Integer, ForeignKey("country.id"))
    country = sqlalchemy.orm.relationship("country", foreign_keys="patent.country_id", backref="patents")

