WALLET_BALANCE_CRON_CLASSES = [
    'exchange.explorer.wallets.crons.GetBitcoinCashWalletBalanceCron',
    'exchange.explorer.wallets.crons.GetTronWalletBalanceCron',
    'exchange.explorer.wallets.crons.GetBitcoinWalletBalanceCron',
    'exchange.explorer.wallets.crons.GetDogecoinWalletBalanceCron',
    'exchange.explorer.wallets.crons.GetLitecoinWalletBalanceCron',
    'exchange.explorer.wallets.crons.GetCardanoWalletBalanceCron',
    'exchange.explorer.wallets.crons.GetMoneroWalletBalanceCron',
    'exchange.explorer.wallets.crons.GetAlgorandWalletBalanceCron',
    'exchange.explorer.wallets.crons.GetFlowWalletBalanceCron',
    'exchange.explorer.wallets.crons.GetFilecoinWalletBalanceCron',
    'exchange.explorer.wallets.crons.GetArbitrumWalletBalanceCron',
    'exchange.explorer.wallets.crons.GetAptosWalletBalanceCron',
    'exchange.explorer.wallets.crons.GetElrondWalletBalanceCron',
    'exchange.explorer.wallets.crons.GetSolanaWalletBalanceCron',
]

WALLET_TXS_CRON_CLASSES = [
    'exchange.explorer.wallets.crons.GetBitcoinCashWalletTxsCron',
    'exchange.explorer.wallets.crons.GetTronWalletTxsCron',
    'exchange.explorer.wallets.crons.GetBitcoinWalletTxsCron',
    'exchange.explorer.wallets.crons.GetDogecoinWalletTxsCron',
    'exchange.explorer.wallets.crons.GetLitecoinWalletTxsCron',
    'exchange.explorer.wallets.crons.GetCardanoWalletTxsCron',
    'exchange.explorer.wallets.crons.GetMoneroWalletTxsCron',
    'exchange.explorer.wallets.crons.GetAlgorandWalletTxsCron',
    'exchange.explorer.wallets.crons.GetFlowWalletTxsCron',
    'exchange.explorer.wallets.crons.GetFilecoinWalletTxsCron',
    'exchange.explorer.wallets.crons.GetArbitrumWalletTxsCron',
    'exchange.explorer.wallets.crons.GetAptosWalletTxsCron',
    'exchange.explorer.wallets.crons.GetElrondWalletTxsCron',
    'exchange.explorer.wallets.crons.GetSolanaWalletTxsCron',
]

BLOCK_TXS_CRON_CLASSES = [
    'exchange.explorer.blocks.crons.get_block_txs.GetBitcoinCashBlockTxsCron',
    'exchange.explorer.blocks.crons.get_block_txs.GetTronBlockTxsCron',
    'exchange.explorer.blocks.crons.get_block_txs.GetBitcoinBlockTxsCron',
    'exchange.explorer.blocks.crons.get_block_txs.GetDogecoinBlockTxsCron',
    'exchange.explorer.blocks.crons.get_block_txs.GetLitecoinBlockTxsCron',
    'exchange.explorer.blocks.crons.get_block_txs.GetCardanoBlockTxsCron',
    'exchange.explorer.blocks.crons.get_block_txs.GetMoneroBlockTxsCron',
    'exchange.explorer.blocks.crons.get_block_txs.GetAlgorandBlockTxsCron',
    'exchange.explorer.blocks.crons.get_block_txs.GetFlowBlockTxsCron',
    'exchange.explorer.blocks.crons.get_block_txs.GetFilecoinBlockTxsCron',
    'exchange.explorer.blocks.crons.get_block_txs.GetArbitrumBlockTxsCron',
    'exchange.explorer.blocks.crons.get_block_txs.GetAptosBlockTxsCron',
    'exchange.explorer.blocks.crons.get_block_txs.GetElrondBlockTxsCron',
    'exchange.explorer.blocks.crons.get_block_txs.GetSolanaBlockTxsCron',
    'exchange.explorer.blocks.crons.delete_block_txs.DeleteFilecoinBlockTxsCron',
]

RECHECK_BLOCK_TXS_CRON_CLASSES = [
    'exchange.explorer.blocks.crons.recheck_block_txs.GetFilecoinRecheckBlockTxsCron',
    'exchange.explorer.blocks.crons.recheck_block_txs.GetFlowRecheckBlockTxsCron',
    'exchange.explorer.blocks.crons.recheck_block_txs.GetNearRecheckBlockTxsCron',
    'exchange.explorer.blocks.crons.recheck_block_txs.GetSolanaRecheckBlockTxsCron',
    'exchange.explorer.blocks.crons.recheck_block_txs.GetCardanoRecheckBlockTxsCron',
]

STAKING_REWARDS_CLEANUP_CRON_CLASSES = [
    'exchange.explorer.staking.crons.cleanup_rewards.CleanupStakingRewardsCron',
]

CRON_CLASSES = (WALLET_BALANCE_CRON_CLASSES + WALLET_TXS_CRON_CLASSES + BLOCK_TXS_CRON_CLASSES
                + RECHECK_BLOCK_TXS_CRON_CLASSES + STAKING_REWARDS_CLEANUP_CRON_CLASSES)

DJANGO_CRON_LOCK_TIME = 30 * 60  # 30 minutes
