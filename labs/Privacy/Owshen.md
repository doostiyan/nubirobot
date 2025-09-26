# :ocean: Owshen Network - v0.2.0

# Thinking loudly!

 - Airdrop DIVE to all Ethereum accounts
 - Burn ETH and earn DIVE
 - Swap DIVE with ETH

```solidity
contract Owshen {
    function dive(bytes32 burnNullifier, Proof proof, bytes32 commitment) {
        // Mint DIVE according to the amount ETH burnt, create a new commitment in the Owshen merkle-tree
    }

    function send(bytes32 nullifier, Proof proof, bytes32 commitment) {
        // Send DIVE by consuming the nullifier and creating a new commitment
    }

    function buy(bytes32 nullifier, address dst, uint amount, Proof proof, bytes32 commitment) {
        // Consume nullifier if sender has sent `amount` eth
        // Transfer to `dst` `amount` ETH
        // Create a new commitment, transferring the ownership of the consumed nullifier
    }
}
```

## Abstract

Owshen is the very first implementation of an ***Anonymity Marketplace***. An Anonymity Marketplace is a market in which users metaphorically sell their identities, by mixing their identity into an anonymity pool. People who use this anonymity pool for the purpose of making their actions private (Buyers) will pay those who join the pool merely for increasing the size of the pool (Sellers). A large number of sellers will bring more buyers to the market (Given that the pool has got bigger thus more private), and a large number of buyers will bring more sellers (Since it gets very profitable to join as a seller). This whitepaper will discuss a practical implementation of such system using the help of zkSNARKs, and will analyze the dynamics of an Anonymity Marketplace.

Keywords: Privacy, Mixing, zkSNARK

## Introduction

Launched in 2009, Bitcoin was the first cryptocurrency to use a decentralized blockchain to record transactions. Users were identified by alphanumeric addresses, claiming to provide some degree of pseudonymity. While transaction details were visible, the real-world identities of users remained private unless they were voluntarily disclosed. The advance of chain analysis methods made it much easier to find the source and destination of transactions, breaking the privacy guarantees that Bitcoin claimed to have in the first place.

Right after Bitcoin, many cryptocurrency projects were built and introduced, bringing shinier privacy techniques on the table. The essence of many of those privacy techniques were essentially the same. They were trying to gather a lot of transactions together, and mix them into a single, hard to analyze, transaction. This is known as a CoinJoin in UTXO cryptocurrencies like Bitcoin.

A significant concern in private cryptocurrencies, is the size of their anonymity sets. An anonymity set refers to the group of users or participants from which a particular transaction can originate, making it challenging to determine the true source of that transaction. The larger the anonymity set, the more difficult it becomes to trace specific transactions back to their origin. On the other hand, if the anonymity set is small, it reduces the effectiveness of privacy measures and increases the risk of transaction tracing. No matter how good and secure the privacy protocol is, if there are very few people using it, there is no privacy. 

The anonymity set can have different meanings in different privacy-oriented currencies. In case of a CoinJoin, the anonymity set is the users who participate in the CoinJoin. In case of a TornadoCash-style mixing pool on Etheruem, the anonymity-set is the users who have interactions with the pool's smart contract, and in case of a whole private cryptocurrency like Monero, the anonymity set is the users who use Monero.

Knowing the importance of the anonymity sets in privacy-preserving cryptocurrencies, we tried to design a incentive model that encourages people to join an anonymity-set even when they do not need the privacy guarantees that the pool gives to them. We designed our model as a TornadoCash-style smart contract deployed on a blockchain which has massive number of users. Our implmentation is almost identical with TornadoCash with some key differences:

- There will be two kind of people using this platform:
    - **Buyers**: They want to anonymize their funds.
    - **Sellers**: They will help others to anonymize their funds.
- People deposit a fixed amount of tokens to the contract, plus an anonymizing fee. E.g. 1ETH + 0.1ETH (Anonymizing fee)
    - **NOTE:** Both **Buyers** and **Sellers** deposit same amount of ETH (1.1ETH) to the contract, so they are not distinguishable from the outside)
    - We will also keep track of the number of deposits: `active_deposits += 1;`
- The deposit commitments are saved on a sparse merkle tree besides their deposit date (Block number $b$) -> Leaf value: $H(b + H(s | 0))$:
    - Secret $s$
    - Commitment: $H(s | 0)$
    - Nullifier: $H(s | 1)$
    - Reward Nullifier: $H(s | 2 | m)$ (Where $m$ is the number of months past since the initial deposit)
- There will be two types of withdrawals:
    - **Withdrawal:** Prove that you know $s$ (Secret) where $H(s | 0)$ (Commitment to the secret) exists in the tree and its nullifier is $H(s | 1)$ which is not previously withdrawn, you will receive 1.0ETH. After revealing the nullifier, the [nullifier]th leaf of another sparse merkle tree will be flagged true.
        - The number of active deposits decreases on withdrawals: `active_deposits -= 1;`
    - **Reward Withdrawal:** Prove that you know $s$ (Secret) where $H(s | 0)$ (Commitment) exists in the tree, which its reward-nullifier is $H(s | 2 | m)$, and coinage is above a threshold, but $H(s | 1)$ (The nullifier of that secret) does not exist in nullifier sparse-merkle-tree (I.e. tokens are held and not withdrawn). Then you will receive `address(this).balance / active_deposits` worth of ETH. Notice that you can request a reward after every month, since a new reward-nullifier gets withdrawable for you per month you keep your funds on the contract. You can deposit once and have an steady stream of rewards which get withdrawable every month.

### Security analysis

 - Input transactions are all 1.1ETH, so people can't tell whether an input is a Buyer or Seller
 - Majority of output transactions are all 1.0ETH, so people can't tell whether an output is a Buyer's output or part of Seller's reward.
 - Some output transactions will be (0.1 + r)ETH, which means that output belongs to an Seller, but people won't know it corresponds to which input.

## Protocol Extensions

Assuming that the protocol has attracted a large number of users because of its incentive model, it may make sense to support more advanced operations inside the pool too, decreasing the need for people to exit the pool.

### Coin transfers

A TornadoCash/Zcash-style mixing pool can also be considered as a ***private UTXO model***, where nullifiers are inputs of transactions, and commitments are outputs. In order to do simple token transfers in this scheme, one need to burn a nullifier(s) and create a new commitment(s).

### Coin split/merge

Originally, people were using fixed size coins in both input/output sides of the mixing pool. We argue that, protocol will remain secure even if only one side of the pool has fixed size coins. (E.g. imagine only allowing fixed 1.1ETH coins as inputs, but allowing outputs with arbitrary amounts, e.g. 0.1234ETH)

In a UTXO model, you can have multiple inputs and multiple outputs in a single transfer. In a private environment, zkSNARKs can help us make sure the sum of the inputs is equal with the sum of the outputs. By supporting multi-input (Nullifer) multi-output (Commitment) transactions, we can support transfer of assets in arbitrary amounts within the pool.

Given that the protocol only supports deposits of fixed amount 1.0ETH, Alice can send 1.6ETH to Bob by burning two nullifers of amount 1.0ETH and creating two commitments of amounts 1.6ETH (That belongs to Bob) and 0.4ETH (That is the remainder of the transaction given back to Alice)

`Alice (1.0ETH) + Alice (1.0ETH) -> Alice (0.4ETH) + Bob (1.6ETH)`

The amounts of transfers can remain private, since the commitments may store the hashed version of amount data.

### Custom tokens

Our pool may support deposits of custom assets too (ERC-20 and NFTs). In case of token transfers, zkSNARKs will make sure that the token types in both sides of the UTXO transfers are of the same type. Just like the way we hide amounts in the transfers, token types could also remain private by embedding them into the preimage of commitment hashes.

Sellers who contribute to the anonymity pool of token X, will receive anonymizing fees that are gained during deposits of token X.

### Swapping

Swapping two fungible assets can be described as a UTXO transfer with two inputs (Nullifers) and 4 outputs (Commitments) where 2 of the 4 outputs are the remainders of the swaps.

As an example, let's say Alice has a coin of worth 1.0ETH and Bob has a coin of worth 100.0DAI in the pool. Bob wants to buy 0.1ETH from Alice for 40.0DAI. The UTXO defintion of this swap can be described as:

`Alice (1.0ETH) + Bob (100.0DAI) -> Alice (40.0DAI) + Bob (0.1ETH) + Alice (0.9ETH) + Bob (60.0DAI)`

Alice and Bob should both generate proofs proving their ownership of their corresponding nullifier, besides acknowledging the transaction.

By putting time-locks on our zkSNARK proofs, we can expire the swap requests in case the other party of a swap refuses to sign (Generate proof) for the swap.

## Calculations

Here we provide calculation of Seller profits in case of different number of Buyers and Sellers. 

| Buyers |   Sellers   |  Input  | Buyers Output | Anonymizer Reward |
|--------|-------------|---------|---------------|-------------------|
|    0   |     100     |   110$  |      0$       |  110/100 = 1.1$   |
|    1   |      99     |   110$  |      1$       |   109/99 = 1.101$ |
|   50   |      50     |   110$  |     50$       |    60/50 = 1.2$   |
|   99   |       1     |   110$  |     99$       |     11/1 = 11.0$  |
|  100   |       0     |   110$  |    100$       |         N/A       |

The worst case is when all of the people participating in the protocol are sellers (I.e they are there to get revenue). In this case, they will get 0 reward and they will basically get their original money back.

In case the number of Buyers and Sellers are equal, the profit of a seller is approximately: $\frac{f}{1 + f}$ where $f$ is the anonymizing fee. As an example, if anonymizing fee is 10% of the value deposited, the seller's profit would be: $\frac{0.1}{1+0.1} \simeq  0.091$, around 9%.

And lastly, if the number of Buyers is much higher than the number of Sellers, there will be a big pool of rewards for Sellers to claim. Thus it's in their best interest to join the network as soon as possible and claim those rewards, leading to an increase in the size of the anonymity set, which will make the pool even more private.
