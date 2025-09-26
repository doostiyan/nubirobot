# Anonymity Marketplace (I.e. Incentivized Mixing Platform)

By Keyvan / Hamid

## Abstract

A platform and economic model in which people can mix/sell their identities to users who want to keep their transactions private.

This will create incentive for people to join a cryptocurrency mixing pool, leading to pools with larger active-sets and stronger privacy guarantees.

## Structure

- There will be two kind of people using this platform:
    - **Users**: They want to anonymize their funds.
    - **Anonymizers**: They will help others to anonymize their funds
- People deposit to the contract: 1ETH + 0.1ETH (Anonymizing fee)
    - **NOTE:** Both **Users** and **Anonymizers** deposit same amount of ETH (1.1ETH) to the contract, so they are not distinguishable :wink:)
    - `active_deposits += 1;`
- Their deposit commitment is saved on the merkle tree besides its deposit date (Block number) -> Leaf value: `H(block_num + H(s | 0))`
    - Secret `s`
    - Commitment: `H(s | 0)`
    - Nullifier: `H(s | 1)`
    - Reward Nullifier: `H(s | 2 | number_of_months_passed)`
- There will be two types of withdrawals:
    - **Withdrawal:** Prove that you know `s` where `H(s | 0)` exists in the tree and its nullifier is `H(s | 1)` which is not previously withdrawn, you will receive 1.0ETH. After revealing nullifier, it will be stored on a sparse-merkle-tree.
        - `active_deposits -= 1;`
    - **Reward Withdrawal:** Prove that you know `s` where `H(s | 0)` exists in the tree, and its reward-nullifier is `H(s | 2)`, and coinage is above a threshold, and the `H(s | 1`) does not exist in nullifier sparse-merkle-tree (I.e. tokens are held and not withdrawn). Then you will receive `address(this).balance / active_deposits` worth of ETH.
- Security analysis
    - Input transactions are all 1.1ETH, so people can't tell whether an input is a User or Anonymizer
    - Majority of output transactions are all 1.0ETH, so people can't tell whether an output is a User's output or part of Anonymizers reward.
    - Some output transactions will be 0.2ETH, which means that output belongs to an Anonymizer, but people won't know it corresponds to which input.
    

## Considerations
 - We can combine 5x0.2 reward transactions and give 1.0ETH outputs to further increase the anonymity.
 - We can use DAI instead of ETH as our native token
 - What if there are more **Anonymizers** than **Users**?
     - Anonymizers won't get much profit, they will get their original money back in the worst case (When all people are Anonymizer and no one is a user)
 - What if there are more **Users** than **Anonymizers**?
     - Anonymizers will get a lot of profit. More Anonymizers will be encouraged to join the network, which will improve privacy, which will also encourage more users to join!
 - Imagine I am a validator who has been locking my fund in the contracts for more than a month. New members will join the network and increase `active_deposits`, which will decrease my reward. Isn't that unfair?
     - It may seem unfair, but notice that those who join the network are increasing the `address(this).balance` too, so the effect is minimal. And also, those who join the network are bringing added-value (Improved privacy) which will eventually bring more Users + liquidity to the network, increasing your profit.
  - Users can pay their withdrawal/send gas fees through a Account-Abstraction paymaster?
  - A paymaster can live inside the mixer

## Calculations

Calculation of Anonymizer rewards in case of different number of Users and Anonymizers:

| Users | Anonymizers |  Input  | Users Output | Anonymizer Reward |
|-------|-------------|---------|--------------|-------------------|
|   0   |     100     |   110$  |      0$      |  110/100 = 1.1$   |
|   1   |      99     |   110$  |      1$      |   109/99 = 1.101$ |
|  50   |      50     |   110$  |     50$      |    60/50 = 1.2$   |
|  99   |       1     |   110$  |     99$      |     11/1 = 11.0$  |
| 100   |       0     |   110$  |    100$      |         N/A       |

## Contract

```solidity

contract AnonymityMarket {

    // Commitment tree
    bytes32 commitmentRoot;
    uint commitmentCounter;

    // Nullifier tree (Sparse Merkle Tree)
    bytes32 nullifierRoot;

    uint activeDeposits;

    // Nullifier lists
    mapping (bytes32 => bool) public nullifiers;
    mapping (bytes32 => bool) public rewardNullifiers;

    constructor() public {
        commitmentCounter = 0;
        activeDeposits = 0;
    }

    // Unshielded to Shielded
    function deposit(bytes32 commitment) external {
        require(msg.value == 1.1 ether, "invalid paid amount");

        bytes32 leaf = keccak256(abi.encodePacked(commitment, block.number));
        // Update `commitmentRoot`, i.e.e put leaf on `commitmentCounter`th index of commitment tree
        commitmentCounter += 1;
        activeDeposits += 1;
    }

    // Shielded to Unshielded
    function withdraw(bytes32 nullifier, bytes proof) external {
        require(nullifiers(nullifier) == false);

        // Check zk proof that there exists a commitment in the tree that its nullifier is `nullifier`
        require(checkProof(proof, commitmentRoot, nullifier));

        bool sent = msg.sender.send(1 ether);
        require(sent, "Failed to send Ether");

        // Set `nullifier`th leaf of the nullifier sparse-merkle-tree to 1 and update `nullifierRoot`
        
        activeDeposits -= 1;
        nullifiers[nullifier] = true;
    }

    function withdrawReward(bytes32 rewardNullifier, bytes proof) external {
        require(nullifiers(rewardNullifier) == false);

        // Check zk proof that there exists a commitment in the tree that its rewardNullifier is `rewardNullifier`
        // its age is above N months and its nullifier does not exist in the nullifier tree. N withdrawals can
        // be made with different rewardNullifiers: H(s | 2 | n) where 0<=n<N
        require(checkProof(proof, commitmentRoot, rewardNullifier, block.number, nullifierRoot));

        bool sent = msg.sender.send((address(this).balance / activeDeposits) - 1 ether);
        require(sent, "Failed to send Ether");
        rewardNullifiers[rewardNullifier] = true;
    }

    ///////////////////////////////////
    // ABOVE FUNCTIONS ARE ALREADY GOOD AS A COMPLETE PRODUCT, WE CAN HAVE EXTRA FEATURES:
    ///////////////////////////////////

    // Shielded to Shielded
    function send(bytes32 nullifier, bytes32 newCommitment, bytes proof) external {
        require(nullifiers(nullifier) == false);

        // Check zk proof that there exists a commitment in the tree that its nullifier is `nullifier`
        require(checkProof(proof, commitmentRoot, nullifier));

        bytes32 leaf = keccak256(abi.encodePacked(newCommitment, block.number));
        // Update `commitmentRoot`, i.e put leaf on `commitmentCounter`th index of commitment tree
        commitmentCounter += 1;

        // Set `nullifier`th leaf of the nullifier sparse-merkle-tree to 1 and update `nullifierRoot`

        nullifiers[nullifier] = true;

        // WARN: THE OWNER OF newCommitment's SECRET MAY WITHDRAW A REWARD?!
    }

    function swap(bytes32 nullifierA, bytes32 nullifierB, bytes32 commitA, bytes32 commitB, bytes proofExistenceA, bytes proofExistenceB, bytes proofSignA, bytes proofSignB) external {
        require(nullifiers(nullifierA) == false);
        require(nullifiers(nullifierB) == false);
        // Check zk proof that there exists a commitment in the tree that its nullifier is `nullifierA` and `nullifierB`
        require(checkProof(proofExistenceA, commitmentRoot, nullifierA));
        require(checkProof(proofExistenceB, commitmentRoot, nullifierB));

        // I know an s which H(s | 0) is nullifierA and I commit to nullifierB and vice versa
        require(checkProof(proofSignA, nullifierA, nullifierB));
        require(checkProof(proofSignB, nullifierB, nullifierA));

        // TODO: make sure commitA and commitB values are reversed?

        // Set `nullifierA`th and `nullifierB`th leaf of the nullifier sparse-merkle-tree to 1 and update `nullifierRoot`

        nullifiers[nullifierA] = true;
        nullifiers[nullifierB] = true;
    }
}

```

