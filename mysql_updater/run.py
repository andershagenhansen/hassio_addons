import json
import time
import mysql.connector
import logging

OPTIONS_FILE = "/data/options.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

def load_options():
    with open(OPTIONS_FILE) as f:
        return json.load(f)

def mysql_connect(cfg):
    return mysql.connector.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        connection_timeout=5
    )

def test_connection(mysql_cfg):
    logging.info("Testing MySQL connection...")
    try:
        conn = mysql_connect(mysql_cfg)
        conn.close()
        logging.info("✅ MySQL connection successful")
    except Exception as e:
        logging.error("❌ MySQL connection failed: %s", e)

def run_update(cfg):
    mysql_cfg = cfg["mysql"]
    sensor_name = cfg["statistics"]["sensor_name"]

    conn = mysql_connect(mysql_cfg)
    cursor = conn.cursor()

    query = """
    UPDATE statistics
       SET start_ts = start_ts - 3600,
           wasupdated = 1
     WHERE wasupdated IS NULL
       AND metadata_id = (
            SELECT id
              FROM statistics_meta
             WHERE statistic_id = %s
       )
    """

    cursor.execute(query, (sensor_name,))
    affected = cursor.rowcount

    conn.commit()
    cursor.close()
    conn.close()

    logging.info(
        "✅ Statistics updated for sensor '%s' (rows affected=%s)",
        sensor_name,
        affected
    )

def main():
    logging.info("✅ MySQL Periodic Updater started")

    while True:
        cfg = load_options()

        if cfg.get("test_connection", False):
            test_connection(cfg["mysql"])

        try:
            run_update(cfg)
        except Exception as e:
            logging.error("Update failed: %s", e)

        interval = max(10, cfg.get("interval_seconds", 300))
        time.sleep(interval)

if __name__ == "__main__":
    main()
