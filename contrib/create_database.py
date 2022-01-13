import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def create_database():
    try:
        con = psycopg2.connect(host="postgres", database="postgres", user="postgres", password="postgres")
        con.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    except Exception as e:
        print(e)
        raise Exception("Could not connect to database")

    cur = con.cursor()

    try:
        cur.execute("CREATE USER connect WITH PASSWORD 'connect'")
        cur.execute("ALTER ROLE connect WITH SUPERUSER")
        cur.execute("CREATE DATABASE connect")
    except Exception as e:
        raise(e)
    # close connection
    cur.close()
    con.close()

if __name__ == "__main__":
    create_database()
