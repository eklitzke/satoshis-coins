import argparse
import json
import datetime
import sys
from typing import Any, Dict, List

from bitcoinrpc.authproxy import AuthServiceProxy


class CircularBuffer:
    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.position = 0
        self.items = []  # type: List[Any]

    def insert(self, item: Any) -> bool:
        """Insert an item into the buffer.

        Return True if the buffer is full, False otherwise.
        """
        full = len(self.items) == self.capacity
        if full:
            self.items[self.position] = item
            self.position = (self.position + 1) % self.capacity
        else:
            self.items.append(item)
        return full

    def tail(self) -> Any:
        """Get the oldest item in the buffer."""
        return self.items[self.position]


class BlockFetcher:
    """Block iterator that batches RPC calls."""

    def __init__(self,
                 rpc_connection: AuthServiceProxy,
                 cutoff_delta: datetime.timedelta,
                 scan_coinbase=False,
                 batch_size=100) -> None:
        self.rpc_connection = rpc_connection
        self.height = 0
        self.cutoff = None
        self.cutoff_delta = cutoff_delta
        self.blocks = []  # type: List[Dict[str, Any]]
        self.scan_coinbase = scan_coinbase
        self.batch_size = batch_size

    def block_time(self, block: Dict[str, Any]) -> datetime.datetime:
        """Get the datetime timestamp for a block."""
        unix_time = int(block['time'])
        return datetime.datetime.fromtimestamp(unix_time)

    def _fetch_blocks(self):
        assert self.blocks == []
        block_hashes = self.rpc_connection.batch_(
            ['getblockhash', h]
            for h in range(self.height, self.height + self.batch_size))
        self.height += self.batch_size
        if self.scan_coinbase:
            commands = (['getblock', h, 2] for h in block_hashes)
        else:
            commands = (['getblock', h] for h in block_hashes)
        self.blocks = self.rpc_connection.batch_(commands)

    def __iter__(self):
        assert self.height == 0
        self._fetch_blocks()
        self.cutoff = self.block_time(self.blocks[0]) + self.cutoff_delta
        return self

    def __next__(self):
        assert self.height != 0
        if not self.blocks:
            self._fetch_blocks()
        block = self.blocks.pop(0)
        if self.block_time(block) >= self.cutoff:
            raise StopIteration
        return block


def estimate_hash_rate(difficulty: float, seconds: float) -> float:
    """Estimate network hashes/sec based on the difficulty and block interval.

    This uses the algorithm described at https://en.bitcoin.it/wiki/Difficulty.
    """
    expected_hashes = difficulty * (1 << 48) / 0xffff
    return expected_hashes / seconds


def block_reward(block: Dict[str, Any], scan_coinbase: bool) -> float:
    """Get the block reward at a given height."""
    if not scan_coinbase:
        epoch = int(block(['height'])) // 210000
        return 50 * 0.5**epoch
    for tx in block['tx']:
        if any('coinbase' in vin for vin in tx['vin']):
            return sum(float(vout['value']) for vout in tx['vout'])
    assert False  # not reached


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-s',
        '--scan-coinbase',
        action='store_true',
        help='Scan transactions to get coinbase rewards')
    parser.add_argument(
        '-d', '--days', type=int, default=400, help='Days to analyze')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('url')
    args = parser.parse_args()

    info = []
    rpc_connection = AuthServiceProxy(args.url)
    times = CircularBuffer(2016)
    cutoff_delta = datetime.timedelta(days=args.days)
    fetcher = BlockFetcher(rpc_connection, cutoff_delta, args.scan_coinbase)
    for block in fetcher:
        timestamp = fetcher.block_time(block)
        difficulty = float(block['difficulty'])
        time_per_block, hash_rate = None, None
        if times.insert(timestamp):
            elapsed = (timestamp - times.tail()).total_seconds()
            time_per_block = elapsed / times.capacity
            hash_rate = estimate_hash_rate(difficulty, time_per_block)
        height = int(block['height'])
        info.append({
            'height': height,
            'time': int(timestamp.timestamp()),
            'difficulty': difficulty,
            'interval': time_per_block,
            'reward': block_reward(block, args.scan_coinbase),
            'hashrate': hash_rate,
        })

    outfile = open(args.output, 'w') if args.output else sys.stdout
    json.dump(info, outfile)
    outfile.write('\n')


if __name__ == '__main__':
    main()
