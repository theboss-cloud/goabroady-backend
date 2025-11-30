# check_tables.py
from sqlalchemy import inspect, create_engine
from config import Config

url = Config.SQLALCHEMY_DATABASE_URI
print("using DB:", url)

eng = create_engine(url, future=True)
ins = inspect(eng)
print("tables:", sorted(ins.get_table_names()))
