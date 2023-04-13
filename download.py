import requests
import os
import json
import time
import csv
import datetime
from time import perf_counter
from termcolor import colored
import click


class Logger(object):
    def __init__(self, tag=None, file_path=None, color="cyan"):
        self.tag = tag
        self.file_path = file_path
        self.color = color
        self.start_time = perf_counter()
        if self.file_path is not None:
            os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
            self.fh = open(self.file_path, "w+")

    def __call__(self, *args, **kwargs):
        date_str = colored(f"[{datetime.datetime.now().strftime('%d-%b-%Y %H:%M:%S')}]", color=self.color)
        took_str = colored(f"[{perf_counter() - self.start_time:.4f}]", color=self.color)
        prefix = f"{date_str} {took_str}"
        if self.tag is not None:
            tag_str = colored(f"[{self.tag}]", color=self.color, attrs=["bold"])
            prefix += f" {tag_str}"
        print(f"{prefix}", *args, **kwargs)
        if self.file_path is not None:
            print(f"{prefix}", *args, **kwargs, file=self.fh)

    def reset_timer(self):
        self.start_time = perf_counter()

    def close(self):
        self.fh.close()


class OHLCDownloader(object):
    def __init__(self, interval, save_dir):
        self.interval = interval
        self.save_dir = save_dir
        checkpoints_dir = f"{self.save_dir}/checkpoints"
        os.makedirs(checkpoints_dir, exist_ok=True)

    def fetch(self, token_address, page_size=100, cursor=None):
        url = "https://api.syve.ai/v1/prices_usd"
        body = {
            "filter": {
                "type": "eq",
                "params": {"field": "token_address", "value": token_address},
            },
            "bucket": {"type": "range", "params": {"field": "timestamp", "interval": self.interval}},
            "aggregate": [
                {"type": "open", "params": {"field": "price_usd_token"}},
                {"type": "max", "params": {"field": "price_usd_token"}},
                {"type": "min", "params": {"field": "price_usd_token"}},
                {"type": "close", "params": {"field": "price_usd_token"}},
            ],
            "options": [
                {"type": "size", "params": {"value": page_size}},
                {"type": "sort", "params": {"field": "timestamp", "value": "desc"}},
            ],
        }
        if cursor is not None:
            body["options"].append({"type": "cursor", "params": {"value": cursor}})
        res = requests.post(url, json=body)
        if res.status_code == 429:
            time.sleep(1)
            return self.fetch(token_address, page_size, cursor)
        data = res.json()
        return data

    def generate(self, token_address, page_size=100, max_pages=None, cursor=None):
        curr_page = 1
        while True:
            data = self.fetch(token_address, page_size, cursor)
            if len(data["results"]) == 0:
                break
            else:
                yield data
            if max_pages is not None and curr_page >= max_pages:
                break
            cursor = data["cursor"]["next"]
            curr_page += 1

    def load_cursor(self, checkpoints_path):
        try:
            with open(checkpoints_path, "r") as file:
                cursor = file.readline().strip()
                if cursor:
                    return cursor
                else:
                    return None
        except FileNotFoundError:
            return None

    def update_cursor(self, cursor, checkpoints_path):
        with open(checkpoints_path, "w+") as file:
            file.write(cursor)

    def round(self, x, n):
        return "%s" % float("%.6g" % x)

    def format_records(self, records):
        output = []
        for x in records:
            output.append(
                {
                    "price_open": self.round(x["price_usd_token_open"], 6) if "price_usd_token_open" in x else None,
                    "price_high": self.round(x["price_usd_token_max"], 6) if "price_usd_token_max" in x else None,
                    "price_low": self.round(x["price_usd_token_min"], 6) if "price_usd_token_min" in x else None,
                    "price_close": self.round(x["price_usd_token_close"], 6) if "price_usd_token_close" in x else None,
                    "timestamp": x["timestamp"],
                    "date": x["date_time"],
                }
            )
        return output

    def save_records(self, records, records_path):
        if len(records) == 0:
            return None
        if not os.path.exists(records_path):
            with open(records_path, "w+") as file:
                headers = ",".join(records[0].keys())
                file.write(headers + "\n")
        with open(records_path, "a+") as file:
            for record in records:
                values = ",".join(str(value) for value in record.values())
                file.write(values + "\n")

    def run(self, token_address, page_size=100, max_pages=None):
        log = Logger(f"{token_address}")
        token_address = token_address.lower()
        checkpoints_path = f"{self.save_dir}/checkpoints/{token_address}.txt"
        records_path = f"{self.save_dir}/{token_address}.csv"
        cursor = self.load_cursor(checkpoints_path)
        for data in self.generate(token_address, page_size, max_pages, cursor):
            records = data["results"]
            cursor = data["cursor"]["next"]
            records = self.format_records(records)
            self.save_records(records, records_path)
            self.update_cursor(cursor, checkpoints_path)
            log(f"Downloaded {len(records)} records. Last cursor: {cursor}.")
            time.sleep(1.01)


class TokenMetadataDownloader(object):
    def __init__(self, token_addresses, token_metadata_path):
        self.token_addresses = token_addresses
        self.token_metadata_path = token_metadata_path

    def batch(self, a: list, sz: int):
        i = 0
        while i < len(a):
            j = i + sz
            yield a[i:j]
            i += sz

    def save_records(self, records, records_path):
        if len(records) == 0:
            return None
        if not os.path.exists(records_path):
            with open(records_path, "w+") as file:
                headers = ",".join(records[0].keys())
                file.write(headers + "\n")
        with open(records_path, "a+") as file:
            for record in records:
                values = ",".join(str(value) for value in record.values())
                file.write(values + "\n")

    def get_visited_addresses(self):
        visited_addresses = set()
        if os.path.exists(self.token_metadata_path):
            with open(self.token_metadata_path, "r") as f:
                reader = csv.reader(f, delimiter=",")
                _ = next(reader)  # skip header
                for row in reader:
                    visited_addresses.add(row[0])
        return visited_addresses

    def run(self):
        visited_addresses = self.get_visited_addresses()
        print("Running token metadata downloader... Number of addresses visited:", len(visited_addresses))
        self.token_addresses = [x for x in self.token_addresses if x not in visited_addresses]
        total_saved = len(visited_addresses)
        print("Total to download: ", len(self.token_addresses))
        for b in self.batch(self.token_addresses, 10):
            token_addresses_csv = ",".join(b)
            res = requests.get(f"https://api.syve.ai/v1/metadata/erc20?address={token_addresses_csv}")
            res_data = res.json()
            time.sleep(1.01)
            records = res_data["results"]["results"]
            self.save_records(records, self.token_metadata_path)
            total_saved += len(records)
            msg = f"Finished downloading metadata for {len(records)} tokens"
            msg += f" - Total: {total_saved}/{len(self.token_addresses)}."
            print(msg)


def fetch_token_list():
    token_list = json.load(open(f"{os.environ['REPO_DIR']}/data/token_list.json"))
    return token_list


def download_ohlc(token_list, resolution="1m"):
    downloader = OHLCDownloader(interval=resolution, save_dir=f"{os.environ['REPO_DIR']}/data/ohlc/{resolution}")
    for i, token_address in enumerate(token_list):
        downloader.run(token_address=token_address, page_size=100000, max_pages=None)
        print(f"Finished downloading token {i + 1}/{len(token_list)} (address = {token_address}).")


def download_token_metadata(token_list):
    downloader = TokenMetadataDownloader(token_list, f"{os.environ['REPO_DIR']}/data/token_metadata.csv")
    downloader.run()


@click.command()
@click.option("--metadata", is_flag=True)
@click.option("--ohlc", is_flag=True)
@click.option("--resolution", type=str, default="1m")
def main(metadata, ohlc, resolution):
    if not metadata and not ohlc:
        print("Please specify --metadata or --ohlc.")
        return None
    os.environ["REPO_DIR"] = os.getcwd()
    token_list = fetch_token_list()
    if metadata:
        download_token_metadata(token_list)
    if ohlc:
        download_ohlc(token_list, resolution=resolution)


if __name__ == "__main__":
    main()
