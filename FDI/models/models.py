import os

from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Boolean
from sqlalchemy.ext.declarative import as_declarative, declared_attr, declarative_base
import sqlalchemy.orm


engine = create_engine('sqlite:///{path}/db.sqlite3'.format(path=os.path.dirname(os.path.dirname(__file__)))
                       , encoding="utf8", echo=False)


Base = declarative_base()


class Country(Base):
    __tablename__ = "Country"

    id = Column("id", Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False)
    fdi_in_total = Column(Float, default=0)
    fdi_out_total = Column(Float, default=0)

    fdi_in = sqlalchemy.orm.relationship("FDI", back_populates="to_c", foreign_keys="FDI.to_c_id")
    fdi_out = sqlalchemy.orm.relationship("FDI", back_populates="from_c", foreign_keys="FDI.from_c_id")

    is_g20 = Column(Boolean, default=False)
    is_oecd = Column(Boolean, default=False)

    def __repr__(self):
        return "<Country: %s>" % self.name


class FDI(Base):
    __tablename__ = "FDI"

    id = Column("id", Integer, primary_key=True, autoincrement=True)
    from_c_id = Column(Integer, ForeignKey("Country.id"))
    from_c = sqlalchemy.orm.relationship("Country", foreign_keys="FDI.from_c_id")

    to_c_id = Column(Integer, ForeignKey("Country.id"))
    to_c = sqlalchemy.orm.relationship("Country", foreign_keys="FDI.to_c_id")

    value = Column(Float, default=0)
    year = Column(Integer, default=2000)

    data_type = Column(String(20))


DBSession = sqlalchemy.orm.sessionmaker(bind=engine)


def new_session():
    return DBSession()
