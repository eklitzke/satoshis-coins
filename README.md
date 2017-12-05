This is a utility that looks at the early hash rate of the Bitcoin network and
exports data as JSON. To run this you'll need a local full Bitcoin Core node.
Then run `pip install -r requirements.txt` (possibly after creating a
virtualenv) and run `analyze.py` with your RPC username and password:

```bash
# Connects to the local Bitcoin Core node using the given username/password
$ python analyze.py -s http://rpcuser:rpcpassword@127.0.0.1:8332'
```
