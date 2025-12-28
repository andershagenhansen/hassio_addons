import json
import time
import mysql.connector
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

OPTIONS_FILE = "/data/options.json"

def load_options():
    with open(OPTIONS_FILE) as f:
        return json.load(f)

def run_update(cfg):
    conn = mysql.connector.connect(
        host=cfg["mysql_host"],
        port=cfg["mysql_port"],
        user=cfg["mysql_user"],
        password=cfg["mysql_password"],
        database=cfg["mysql_database"],
        autocommit=True
    )

    cursor = conn.cursor()

    query = """
    UPDATE my_table
    SET last_seen = NOW()
    WHERE id = %s
    """

    cursor.execute(query, (cfg["target_id"],))
    affected = cursor.rowcount

    cursor.close()
    conn.close()

    logging.info("Update executed for id=%s (rows affected=%s)", cfg["target_id"], affected)

def main():
    logging.info("MySQL updater started")

    while True:
        try:
            cfg = load_options()
            run_update(cfg)
        except Exception as e:
            logging.error("Error running update: %s", e)

        time.sleep(300)  # 5 minutes

if __name__ == "__main__":
    main()
