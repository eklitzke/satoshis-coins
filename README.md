This is a utility that looks at the early hash rate of the Bitcoin network and
exports data as JSON.

## Methodology

The code is pretty straightforward, it just fetches blocks starting from the
genesis block until enough data has been collected. Two things are worth noting:

 * The timestamps used are the *start* time for each block. Therefore the first
   data point has an indicated time of Jan 3, 2009, even though it includes data
   up to Jan 27, 2009.
 * For simplicity I estimate the network hash rate using the delta from the
   first two blocks in two consecutive difficulty periods. This is technically
   off-by-one from how difficulty is computed in the [reference
   code](https://github.com/bitcoin/bitcoin/blob/master/src/pow.cpp), which
   performs the calculation comparing the first block in the period to the last
   block in the same period. This off-by-one doesn't affect the data analysis in
   any way.

## Running

To run this you'll need a local full Bitcoin Core node. Then run `pip install -r
requirements.txt` (possibly after creating a virtualenv) and run `analyze.py`
with your RPC username and password:

```bash
# Connects to the local Bitcoin Core node using the given username/password
$ python analyze.py -s http://rpcuser:rpcpassword@127.0.0.1:8332'
```
