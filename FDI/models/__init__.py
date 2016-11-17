from models import Country, FDI, Base
from models import engine

Base.metadata.create_all(engine)
