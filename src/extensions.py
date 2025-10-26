from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()

@event.listens_for(Engine, "connect")
def set_sqlite_pragmas(dbapi_conn, conn_record):
    # run this function on database connect
    cur = dbapi_conn.cursor()
    # Enable write-ahead logging and normal synchronization for performance
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA synchronous=NORMAL;")   
    cur.close()
