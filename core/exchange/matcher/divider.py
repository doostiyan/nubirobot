from typing import Dict, List

from exchange.base.decorators import measure_function_execution
from exchange.base.models import Settings
from exchange.market.models import Market
from exchange.matcher.constants import SERIAL_MARKET_SYMBOLS


def _partition_symbols(
    big_partition: list,
    big_dst_currency: str,
    little_partition: list,
    little_dst_currency: str,
) -> List[List[str]]:
    """
    Partitions two lists of symbols into five smaller lists based on their destination currency symbols and size.

    Args:
        big_partition (list[str]): A list of symbols with the `big_dst_currency` symbol.
        big_dst_currency (str): The currency symbol for the `big_partition`.
        little_partition (list[str]): A list of symbols with the `little_dst_currency` symbol.
        little_dst_currency (str): The currency symbol for the `little_partition`.

    Returns:
        List[List[str]]: A list of four lists, each containing partitioned symbols:
        partition 1  ---> half of big partition
        partition 2  ---> half of little partition (doesn't same source with partition 1)
        partition 3  ---> another half of big partition
        partition 4  ---> another half of little partition (same source with partition 1)

             partition1               partition4
        ====================     ====================
             partition2               partition3
        ====================     ====================

    The function ensures that the resulting partitions have balanced sizes and are correctly labeled
    with their respective currency symbols.
    """

    big_partition = [s[: -len(big_dst_currency)] for s in big_partition]
    little_partition = [s[: -len(little_dst_currency)] for s in little_partition]

    split_size = (len(big_partition) + 1) // 2
    partition1 = set(big_partition[:split_size])
    partition3 = set(big_partition[split_size:])

    partition2 = []
    partition4 = []

    for symbol in little_partition:
        if symbol in partition1:
            partition4.append(symbol)
        else:
            partition2.append(symbol)

    partition1 = [p + big_dst_currency for p in partition1]
    partition2 = [p + little_dst_currency for p in partition2]
    partition3 = [p + big_dst_currency for p in partition3]
    partition4 = [p + little_dst_currency for p in partition4]

    return [partition1, partition2, partition3, partition4]


@measure_function_execution(metric_prefix='matcher', metric='partitioningMarkets', metrics_flush_interval=10)
def custom_partition_markets(markets: Dict[str, Market]) -> List[List[Market]]:
    """
    Partitions a dictionary of markets into specific categories based on their destination currency.

    Args:
        markets (Dict[str, Market]): A dictionary where keys are market symbols and values are Market objects.

    Returns:
        List[List[Market]]: A list of lists, where each inner list contains markets belonging to a specific category.

    This function categorizes markets into five groups:

    1. **Non-Concurrent Matcher Markets:** Markets that are not part of the concurrent matcher
                                           are placed in the first partition.
    2. **Concurrent Markets:** Four Partitioned markets based on destination currencies.

    The `_partition_symbols` function is used to further partition the Rial and USDT markets into smaller,
    balanced groups. This ensures efficient processing and avoids overloading any single group.
    """

    is_disabled = Settings.get_value('concurrent_matcher_status', 'enabled') == 'disabled'
    if is_disabled:
        return [markets.values(), [], [], [], []]

    partitions = [[]]
    for symbol in SERIAL_MARKET_SYMBOLS:
        if symbol in markets:
            partitions[0].append(markets[symbol])
            del markets[symbol]

    rial_markets_symbols = []
    usdt_markets_symbols = []

    for key in markets:
        if key.endswith('IRT'):
            rial_markets_symbols.append(key)
        else:
            usdt_markets_symbols.append(key)

    if len(rial_markets_symbols) >= len(usdt_markets_symbols):
        symbols_partitions = _partition_symbols(rial_markets_symbols, 'IRT', usdt_markets_symbols, 'USDT')
    else:
        symbols_partitions = _partition_symbols(usdt_markets_symbols, 'USDT', rial_markets_symbols, 'IRT')

    for symbols in symbols_partitions:
        partitions.append([])
        for symbol in symbols:
            partitions[-1].append(markets[symbol])

    return partitions
