from web3 import Web3, AsyncWeb3
import rlp
from trie import HexaryTrie

PROVIDER = "https://yolo-shy-fog.discover.quiknode.pro/97f7aeb00bc7a8d80c3d4834a16cd9c86b54b552/"

w3 = Web3(Web3.HTTPProvider(PROVIDER))

num = 17962498

b = w3.eth.get_block(num)

t = HexaryTrie(db={})

txs = []
for tx in b.transactions:
    txs.append(w3.eth.get_raw_transaction(tx))

for (i, tx) in enumerate(txs):
    t.set(rlp.encode(i), tx)

print('Verify tx hash: ', b.transactionsRoot.hex() == '0x' + t.root_hash.hex())

for (i, tx) in enumerate(txs):
    proof = t.get_proof(rlp.encode(i))
    print(f'Proving tx #{i}', HexaryTrie.get_from_proof(t.root_hash, rlp.encode(i), proof) == tx)

hashes = [
    b.parentHash.hex(),
    b.sha3Uncles.hex(),
    b.miner,
    b.stateRoot.hex(),
    b.transactionsRoot.hex(),
    b.receiptsRoot.hex(),
    b.logsBloom.hex(),
    hex(b.difficulty),
    hex(b.number),
    hex(b.gasLimit),
    hex(b.gasUsed),
    hex(b.timestamp),
    b.extraData.hex(),
    b.mixHash.hex(),
    b.nonce.hex(),
    hex(b.baseFeePerGas),
    b.withdrawalsRoot.hex(),
]
hashes = ["0x" if h == "0x0" else h for h in hashes]

header = rlp.encode([Web3.to_bytes(hexstr=h) for h in hashes])

print(Web3.keccak(header).hex())
print(b.hash.hex())
