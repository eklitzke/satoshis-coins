import argparse
import json
import datetime
import sys
from typing import Any, Dict, List  # noqa

from bitcoinrpc.authproxy import AuthServiceProxy

DIFFICULTY_INTERVAL = 2016


class BlockFetcher:
    """Block iterator that batches RPC calls."""

    def __init__(self,
                 rpc_connection: AuthServiceProxy,
                 scan_coinbase=False,
                 batch_size=100) -> None:
        self.rpc_connection = rpc_connection
        self.height = 0
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
        return self

    def __next__(self):
        if not self.blocks:
            self._fetch_blocks()
        return self.blocks.pop(0)


def estimate_hash_rate(difficulty: float, seconds: float) -> float:
    """Estimate network hashes/sec based on the difficulty and block interval.

    This uses the algorithm described at https://en.bitcoin.it/wiki/Difficulty.
    """
    expected_hashes = difficulty * (1 << 48) / 0xffff
    return expected_hashes / seconds


def block_reward(block: Dict[str, Any]) -> float:
    """Get the block reward at a given height."""
    for tx in block['tx']:
        if any('coinbase' in vin for vin in tx['vin']):
            return sum(float(vout['value']) for vout in tx['vout'])
    assert False  # not reached


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-m',
        '--mining-rewards',
        action='store_true',
        help='Include mining rewards')
    parser.add_argument(
        '-p',
        '--periods',
        type=int,
        default=28,
        help='Difficulty periods to analyze')
    parser.add_argument('-o', '--output', help='Output file')
    parser.add_argument('url')
    args = parser.parse_args()

    info = []
    rpc_connection = AuthServiceProxy(args.url)
    fetcher = BlockFetcher(rpc_connection, args.mining_rewards)
    for block in fetcher:
        height = int(block['height'])
        if height == 0:
            prev_block = block
            prev_time = fetcher.block_time(block)
            reward = 0
        elif height % DIFFICULTY_INTERVAL == 0:
            cur_time = fetcher.block_time(block)
            elapsed_time = (cur_time - prev_time).total_seconds()
            block_interval = elapsed_time / DIFFICULTY_INTERVAL
            hash_rate = estimate_hash_rate(
                float(prev_block['difficulty']), block_interval)
            data = {
                'height': height,
                'start': int(prev_time.timestamp()),
                'hashrate': hash_rate,
                'interval': block_interval,
            }
            if args.mining_rewards:
                data['reward'] = block_reward(block)
                reward = 0.
            info.append(data)
            if len(info) >= args.periods:
                break
            prev_block = block
            prev_time = cur_time
        if args.mining_rewards:
            reward += block_reward(block)

    outfile = open(args.output, 'w') if args.output else sys.stdout
    json.dump(info, outfile)
    outfile.write('\n')


if __name__ == '__main__':
    main()
