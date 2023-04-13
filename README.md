# crypto-prices-download
For downloading historical 1min resolution OHLC crypto price data

## About

Use this repository to download historical OHLC crypto price data at **any resolution** (1min, 5min, 15min etc.).

- This dataset contains Open-High-Low-Close data for 1926 crypto currency tokens.
- Token prices are denominated in dolalrs.
- The data is downloaded **for free** from Syve (https://www.syve.ai/) using following endpoint https://syve.readme.io/reference/erc20-prices-usd.
- The tokens that were chosen were the top according trading activity on Ethereum based DEXs (e.g. Uniswap).

## Getting started

Getting started requires minimal setup. It's simply a matter of downloading the data and installing the dependencies in `requirements.txt`.

```
REPO_DIR=$HOME
python3 -m venv venv
source venv/bin/activate
pip install -r $REPO_DIR/requirements.txt
```

Note: Feel free to choose another location for $REPO_DIR. `$HOME` is just my preference.

## Downloading OHLC data

```
cd $REPO
source venv/bin/activate
python download.py --ohlc --resolution 1m
```

- `--ohlc` flag is used to specify that you want to download OHLC data.
- `--resolution` is used to specify the resolution of the OHLC data you want to download. Default is 1 minute data. Possible values: `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `6h`, `12h`, `1d`, `1w`.

## Downloading token metadata

- The token metadata file is located at `data/token_metadata.csv`. It contains the `address`, `symbol` and `name` of every token available for download.
- The token metadata file is commited to the repository so you don't need to download it. However, for completeness, you can download it using the following command:

```
cd $REPO
python download.py --metadata
```
