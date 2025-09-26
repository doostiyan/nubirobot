import pytest
from unittest import TestCase
from exchange.base.models import Currencies
from exchange.blockchain.validators import validate_flow_address
from exchange.blockchain.validators import validate_crypto_address, validate_tag, validate_omni_address, \
    validate_crypto_address_v2, validate_memo_v2


class TestValidators(TestCase):
    def test_flow_address_validation(self):
        valid_address1 = '0x6c36d50dd512ef8e'
        valid_address2 = '0xf919ee77447b7497'
        not_valid_address1 = '6c36d50dd512ef8e'
        not_valid_address2 = '0x6c36d50dd512ef8'
        assert validate_flow_address(valid_address1)
        assert validate_flow_address(valid_address2)
        assert not validate_flow_address(not_valid_address1)
        assert not validate_flow_address(not_valid_address2)


@pytest.mark.unit
def test_validate_crypto_address():
    # BTC
    assert validate_crypto_address('1BUgJypb8cU7dfPgpqEq31tUzhyY75NAvD', Currencies.btc)
    assert validate_crypto_address('17NfFbCqFeDgHZXqMZu1GU7ZQTBx3UMt7Y', Currencies.btc)
    assert validate_crypto_address('1Fxei1aBJEZ3DcRimp9Y37oNkMU58KH9xj', Currencies.btc)
    assert validate_crypto_address('1NbwLRhtJ84yJioAK6SBQDTrVgVaqbSjzc', Currencies.btc)
    assert validate_crypto_address('1BDFojQbpfuwLJeynUnb6SoM7gKJnVVid', Currencies.btc)
    assert validate_crypto_address('1WaFam9uCRMUpJNCsEApM8iADkLZxhffE', Currencies.btc)
    assert validate_crypto_address('38rnkh5sL1h7A9Gceb911tURE4sJtkdh3T', Currencies.btc)
    assert validate_crypto_address('3GTemLwtg2LDRLKMKEFhFWsTvFJj9Zq5LU', Currencies.btc)
    assert validate_crypto_address('3HiS6ga7HzNwiqtaLQcHEoN5k38duESTPk', Currencies.btc)
    assert validate_crypto_address('bc1qhhlp9gva56scqmhsr6jfqc9wvtgcyysds3v0vv', Currencies.btc)
    assert validate_crypto_address('bc1qvwemdpdl2pl239d6qqsvucnqd36z0q6qsxa2jv', Currencies.btc)
    assert validate_crypto_address('bc1zw508d6qejxtdg4y5r3zarvaryvg6kdaj', Currencies.btc)
    assert not validate_crypto_address('2RogEdmgs7zzAwnoKMgGRqcZtPF4vh9bpH', Currencies.btc)
    assert not validate_crypto_address('bc1qhhlp9gva56scqmhsr6jfqc9wvtgcyysds3v0wv', Currencies.btc)
    assert not validate_crypto_address('bc1q fggp vs6f rqsj jnnds xsq3 kvqq 66qr 8ztp gv8lt', Currencies.btc)
    assert not validate_crypto_address('1PCcFXFAF88GAWFwBJcSVAjZQEDQSEsNi', Currencies.btc)
    assert not validate_crypto_address('1APx5YVAkyhWQe2EnXQkisGju2PR7uY56h', Currencies.btc)
    assert not validate_crypto_address('1PvaArvVPY6BYA6phPYGtAzGsNmFtVzFEL', Currencies.btc)
    assert not validate_crypto_address('3MmPRs4wQQHqHAcsafhnLvHSR8djvzV8Eg', Currencies.btc)
    assert not validate_crypto_address('بانک صادرات', Currencies.btc)
    assert not validate_crypto_address('123456789', Currencies.btc)
    # ETH
    assert validate_crypto_address('0xf53b6ef397a641efb5625b61d67b20189c5f0cd9', Currencies.eth)
    assert validate_crypto_address('0x2a1EA66AD4242692d5d6f6fd1dA516EC943E36c1', Currencies.eth)
    assert validate_crypto_address('0xDD769307d218AD7Ecc05C19Ce2C8bA772F5d66ba', Currencies.eth)
    assert validate_crypto_address('0x0b877cFA8C9728A632751172f445B1616619a2C8', Currencies.eth)
    assert validate_crypto_address('0x0f31e1c9e1a20027e8aac0e89dd29cf12f8b2a20', Currencies.eth)
    assert not validate_crypto_address('0x31610423E3Bf10A33daC567d10429AfEa9BC2FfE', Currencies.eth)
    # LTC
    assert validate_crypto_address('LKrLtptzSDV1LGysLRaR2izzvM9sfvTry7', Currencies.ltc)
    assert validate_crypto_address('LLdE4yUj7WLp3JEf6pStH6KkosTAFuwUSw', Currencies.ltc)
    assert validate_crypto_address('MJ6Qp7KVxdQx5rG7SeHYregU5g9rmvm4af', Currencies.ltc)
    assert validate_crypto_address('M9Q8FFRRXLpdoAg1zk6xBSD8dfCP2MMLbP', Currencies.ltc)
    assert validate_crypto_address('ltc1qq04956j6hfq9qr6f37yr4m3ztujf9d4jgceq9s', Currencies.ltc)
    assert validate_crypto_address('ltc1ql8hm8kcpxecghr39xgqz6qxsuzgsjel6zha90d', Currencies.ltc)
    assert validate_crypto_address('ltc1qlz0y4u47lcg5uj7ylw5k28v68zun6prk70gdx7', Currencies.ltc)
    assert validate_crypto_address('ltc1qtshtgjfmdyf5xnyk07a86vzkc8mxug9ppc3f64', Currencies.ltc)
    assert validate_crypto_address('ltc1qeu57kxz6s0uqnxp3u9ag9yp22ywuezvq4rnmmj', Currencies.ltc)
    assert validate_crypto_address('ltc1q5jqsxtxgtqj3w6c83nccgzmjyu20juxl6yt506', Currencies.ltc)
    assert not validate_crypto_address('LcgkVvMjwZ2Tf9va6K4jNjgrwmxDwpqP15', Currencies.ltc)
    assert not validate_crypto_address('ltc1qlz0y4u47lcg5uj7ylw5k28v68zun6prk70gdx5', Currencies.ltc)
    assert not validate_crypto_address('ltc1 qlz0y4u47lcg5uj7ylw5k28v68zun6prk70gdx5', Currencies.ltc)
    assert not validate_crypto_address('ltc1 qlz0y4 u47lcg 5uj7ylw5k2 8v68zun6prk70gdx5', Currencies.ltc)
    assert not validate_crypto_address('MVY9PRzSzdo1qgu2exX4mNxuioZiTXMtnF', Currencies.ltc)
    assert not validate_crypto_address('3C9iNbpVjV7bjDP5rN95JKSTkCnb8DB6tN', Currencies.ltc)
    # USDT
    assert validate_crypto_address('0x9824742b36b2ddf54e67c665b14a8d0095aa5b6e', Currencies.usdt, network='ETH')
    assert not validate_crypto_address('0x9824742b36b2ddf54661q165b14a8d0095aa5b6e', Currencies.usdt)
    # OMNI USDT
    assert validate_omni_address('1MH5MBtCDx7zQMvjUyV6i5voicXyHQecod', Currencies.usdt)
    assert validate_omni_address('3GTemLwtg2LDRLKMKEFhFWsTvFJj9Zq5LU', Currencies.usdt)
    assert not validate_omni_address('bc1qhhlp9gva56scqmhsr6jfqc9wvtgcyysds3v0vv', Currencies.usdt)
    assert not validate_omni_address('1MH5MBtCDx7zQMvjUyV6i5voiccyAQecod', Currencies.usdt)
    # XRP
    assert validate_crypto_address('rpHTHXGZddjVWrVDm7zj7bvXfAJ8FWwt8k', Currencies.xrp)
    assert validate_crypto_address('rEb8TK3gBgk5auZkwc6sHnwrGVJH8DuaLh', Currencies.xrp)
    assert validate_crypto_address('rLW9gnQo7BQhU6igk5keqYnH3TVrCxGRzm', Currencies.xrp)
    assert not validate_crypto_address('rP1afBEfikTz7hIh2ExCDni9W4Bx1dUMRk', Currencies.xrp)
    assert not validate_crypto_address('rwRmyGRoJkHKtojaC8SH2wxsnB2q3yNooB', Currencies.xrp)
    # BCH
    assert validate_crypto_address('1CJnEqJEzowE86mzFrjxKAp5BmhCECpeja', Currencies.bch)
    assert validate_crypto_address('1LTQwgyGb9eWwMshUxeB4n22HZbMhaMwx6', Currencies.bch)
    assert validate_crypto_address('1LcGngw1cpGQ82ffqzZqPS8A7r2SqUdbHu', Currencies.bch)
    assert validate_crypto_address('qqalqllag3yqwmqkxj69h34ulxt9sls50yuqwxtzy6', Currencies.bch)
    assert validate_crypto_address('qr8mxy00llvne2k7mlrmy4es98879ywv9ylcmlnmxg', Currencies.bch)
    assert validate_crypto_address('14FL8TWn3QEbyTk88dgj8UywuMed3iqjCM', Currencies.bch)
    assert validate_crypto_address('1J48ZD2kEtuqeAG3qyzS8fBP3JqAJz59L9', Currencies.bch)
    assert validate_crypto_address('qza3rvtv9rhpsxk88jxqs8v63amcgw6u7vkm6anstd', Currencies.bch)
    assert validate_crypto_address('qza3rvtv9rhpsxk88jxqs8v63amcgw6u7v6q3xxs4n', Currencies.bch)
    assert not validate_crypto_address('simpleledger:qq3eu2e94gr3sxlmueny3wttlyd6xv6qnvyhplwydn', Currencies.bch)
    assert not validate_crypto_address('bitcoincash:qqrxa0h9jqnc7v4wmj9ysetsp3y7w9l36u8gnnjulq', Currencies.bch)
    assert not validate_crypto_address('bitcoincash:qq3eu2e94gr3sxlmueny3wttlyd6xv6qnvgv2ymynd', Currencies.bch)
    assert not validate_crypto_address('1LcGngw1cpGQ82ffqzZqPS8A7r2SqUddHu', Currencies.bch)
    assert not validate_crypto_address('qq3eu2e94gr3sxlmueny3wttlyd6xv6qnv3y5av3cm', Currencies.bch)
    assert not validate_crypto_address('bitcoincash:qq3eu2e94gr3sxlmueny3wttlyd6xv6qnv3y5av3cm', Currencies.bch)
    assert not validate_crypto_address('simpleledger:qq3eu2e94gr3sxlmueny3wttlyd6xv6qnv3y5av3cm', Currencies.bch)
    # BNB
    assert validate_crypto_address('bnb1e5gfm9yt0jvpkyxh6hd2t7x6judmp4usunzg0j', Currencies.bnb)
    assert validate_crypto_address('bnb1990lfutz0f9wza6rsh36ysfwt9xpctxrll884r', Currencies.bnb)
    assert validate_crypto_address('bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gtkgf23', Currencies.bnb)
    assert validate_crypto_address('bnb1wa7g68scff5t0ljg69zypj0e993anywtlfk9cz', Currencies.bnb)
    assert validate_crypto_address('tbnb1a3qrp4wpqesxfk9pd9tl7udq5rwte3m30de0nc', Currencies.bnb, testnet=True)
    assert not validate_crypto_address('bnb1e5gem9yt1jvpkyxh6hd1t7x6judmp4uqunzgwe', Currencies.bnb)
    assert not validate_crypto_address('bnb1zwayqrmknatqsxag5kw346nclnajcc577hhmzg', Currencies.bnb)
    assert not validate_crypto_address('bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gpkgf23', Currencies.bnb)
    assert not validate_crypto_address('tbnb1990lfutz0f9wza6rsh36ysfwt9xpctxrll884r', Currencies.bnb, testnet=True)
    # EOS
    assert validate_crypto_address('nobitexeosw1', Currencies.eos)
    assert validate_crypto_address('binancecleos', Currencies.eos)
    assert validate_crypto_address('hitbtcpayins', Currencies.eos)
    assert validate_crypto_address('luckyfish321', Currencies.eos)
    assert validate_crypto_address('binanceeos', Currencies.eos)
    assert validate_crypto_address('deposit.pro', Currencies.eos)
    assert validate_crypto_address('1nobitexeosw', Currencies.eos)
    assert not validate_crypto_address('Reza222hasan', Currencies.eos)
    assert not validate_crypto_address('bnb1tmljpexn4dm4yrlpl65h32umtppnjkmf5hcs2n', Currencies.eos)
    # XLM
    assert validate_crypto_address('GDY25GPB4E5JKWX7ZWQV6SHVAK4OLKKRGBJZ5X2E3BVW3XKE7XWRZ2PH', Currencies.xlm)
    assert validate_crypto_address('GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A', Currencies.xlm)
    assert validate_crypto_address('GAEI6QWF4KJLL2XLMFHLO5EQZY3GVYRWVTCX3AJQVSUOXXPZWBA7DWVW', Currencies.xlm)
    assert not validate_crypto_address('GAEI6QWF4KJLL2XLMFHLO5EQZY3GVYRWVTCX3AJQVSUOXXPZWBA7DWVY', Currencies.xlm)
    assert not validate_crypto_address('GAHK7EEG2WWH  VKD NT4C EQFZGKF 2LGDSW2IVM4S5DP42RBW3K6BTODB4A', Currencies.xlm)
    assert not validate_crypto_address('GAEI6QWF4KJLQ2XLMFHLO5EQZY3GVYRWVTCX3AJQVSUOXXPZWBA7DWVY', Currencies.xlm)
    assert not validate_crypto_address(' AEI6QWF4KJLQ2XLMFHLO5EQZY3GVYRWVTCX3AJQVSUOXXPZWBA7DWVY', Currencies.xlm)
    assert not validate_crypto_address('XGAEI6QWF4KJLQ2XLMFHLO5EQZY3GVYRWVTCX3AJQVSUOXXPZWBA7DWVY', Currencies.xlm)
    assert not validate_crypto_address('AEI6QWF4KJLQ2XLMFHLO5EQZY3GVYRWVTCX3AJQVSUOXXPZWBA7DWVY', Currencies.xlm)
    # TRX
    assert validate_crypto_address('TGrc7Je5emcrqcuNfjKBoRgGh36WDzd1xL', Currencies.trx)
    assert validate_crypto_address('TNNKa5iEcyXkDcQu6XonwPydddFsNynvGG', Currencies.trx)
    assert not validate_crypto_address('TGrc7Je5emcrqcuNfjKBoRgGh36WDd1xL', Currencies.trx)
    assert not validate_crypto_address('TNNKa5iEcyXkDcQu6XonwPydddFsNynv', Currencies.trx)

    # DOGE
    # Correct addresses
    assert validate_crypto_address('DAnBU2rLkUgQb1ZLBJd6Bm5pZ45RN4TQC4', Currencies.doge)
    assert validate_crypto_address('njscgXBB3HUUTXH7njim1Uw82PF9da4R8k', Currencies.doge)
    assert validate_crypto_address('9t4HBUT4km8LBtm8piHpKX3BJzQvYzZK4a', Currencies.doge)
    assert validate_crypto_address('DBXu2kgc3xtvCUWFcxFE3r9hEYgmuaaCyD', Currencies.doge)
    # Incorrect addresses
    # Checksum invalid
    assert not validate_crypto_address('njscgXBB3HUUTXH7njim1Uw82PF9da4R5k', Currencies.doge)
    assert not validate_crypto_address('9t4HBUT4km8LBtm8piHpKX3BJzQvYzZh4a', Currencies.doge)

    # DOT
    # Correct addresses
    assert validate_crypto_address('13ALHq3vrN9Mwx3UzZnbon2oA33TfM9nepPNZQ1yWnfyUqer', Currencies.dot)
    assert validate_crypto_address('5EcQKVbvPRaJ8kvhxgTcqUnmcbX2HjqMm7JXQ7WifK1xHpKA', Currencies.dot, testnet=True)
    # Incorrect addresses
    assert not validate_crypto_address('5EcQKVbvPRaJ8kvhxgTcqUnmcbX2HjqMm7JXQ7WifK1xHpKA', Currencies.dot)
    assert not validate_crypto_address('13ALHq3vrN9Mwx3UzZnbon2oA33TfM9nepPNZQ1yWnfyUqes', Currencies.dot)
    assert not validate_crypto_address('13ALHq3vrN9Mwx3UzZnbon2oA33TfM9nepPNZQ1yWnfyU', Currencies.dot)
    assert not validate_crypto_address('23ALHq3vrN9Mwx3UzZnbon2oA33TfM9nepPNZQ1yWnfyUqes', Currencies.dot)
    assert not validate_crypto_address('13ALHq3vrN9Mwx3UzZnbon2oA33TfM9nepPNZQ1yWnfyUqer', Currencies.dot, testnet=True)
    assert not validate_crypto_address('5EcQKVbvPRaJ8kvhxgTcqUnmcbX2HjqMm7JXQ7WifK1xHpKB', Currencies.dot, testnet=True)
    assert not validate_crypto_address('5EcQKVbvPRaJ8kvhxgTcqUnmcbX2HjqMm7JXQ7WifK1x', Currencies.dot, testnet=True)


@pytest.mark.slow
def test_validate_crypto_address_bnb():
    # BNB
    assert validate_crypto_address('bnb1e5gfm9yt0jvpkyxh6hd2t7x6judmp4usunzg0j', Currencies.bnb)
    assert validate_crypto_address('bnb1990lfutz0f9wza6rsh36ysfwt9xpctxrll884r', Currencies.bnb)
    assert validate_crypto_address('bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gtkgf23', Currencies.bnb)
    assert validate_crypto_address('bnb1wa7g68scff5t0ljg69zypj0e993anywtlfk9cz', Currencies.bnb)
    assert validate_crypto_address('tbnb1a3qrp4wpqesxfk9pd9tl7udq5rwte3m30de0nc', Currencies.bnb, testnet=True)
    assert not validate_crypto_address('bnb1e5gem9yt1jvpkyxh6hd1t7x6judmp4uqunzgwe', Currencies.bnb)
    assert not validate_crypto_address('bnb1zwayqrmknatqsxag5kw346nclnajcc577hhmzg', Currencies.bnb)
    assert not validate_crypto_address('bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gpkgf23', Currencies.bnb)
    assert not validate_crypto_address('tbnb1990lfutz0f9wza6rsh36ysfwt9xpctxrll884r', Currencies.bnb, testnet=True)


@pytest.mark.unit
def test_btc_address_validation_v2():
    # Correct addresses
    assert validate_crypto_address_v2('1BUgJypb8cU7dfPgpqEq31tUzhyY75NAvD', Currencies.btc) == (True, 'BTC')
    assert validate_crypto_address_v2('17NfFbCqFeDgHZXqMZu1GU7ZQTBx3UMt7Y', Currencies.btc) == (True, 'BTC')
    assert validate_crypto_address_v2('1Fxei1aBJEZ3DcRimp9Y37oNkMU58KH9xj', Currencies.btc) == (True, 'BTC')
    assert validate_crypto_address_v2('1NbwLRhtJ84yJioAK6SBQDTrVgVaqbSjzc', Currencies.btc) == (True, 'BTC')
    assert validate_crypto_address_v2('1BDFojQbpfuwLJeynUnb6SoM7gKJnVVid', Currencies.btc) == (True, 'BTC')
    assert validate_crypto_address_v2('1WaFam9uCRMUpJNCsEApM8iADkLZxhffE', Currencies.btc) == (True, 'BTC')
    assert validate_crypto_address_v2('38rnkh5sL1h7A9Gceb911tURE4sJtkdh3T', Currencies.btc) == (True, 'BTC')
    assert validate_crypto_address_v2('3GTemLwtg2LDRLKMKEFhFWsTvFJj9Zq5LU', Currencies.btc) == (True, 'BTC')
    assert validate_crypto_address_v2('3HiS6ga7HzNwiqtaLQcHEoN5k38duESTPk', Currencies.btc) == (True, 'BTC')
    assert validate_crypto_address_v2('bc1qhhlp9gva56scqmhsr6jfqc9wvtgcyysds3v0vv', Currencies.btc) == (True, 'BTC')
    assert validate_crypto_address_v2('bc1qvwemdpdl2pl239d6qqsvucnqd36z0q6qsxa2jv', Currencies.btc) == (True, 'BTC')
    # Incorrect addresses
    # Version 2 witness address
    assert validate_crypto_address_v2('bc1zw508d6qejxtdg4y5r3zarvaryvg6kdaj', Currencies.btc) == (False, None)
    # First character invalid
    assert validate_crypto_address_v2('2RogEdmgs7zzAwnoKMgGRqcZtPF4vh9bpH', Currencies.btc) == (False, None)
    # Checksum invalid
    assert validate_crypto_address_v2('bc1qhhlp9gva56scqmhsr6jfqc9wvtgcyysds3v0wv', Currencies.btc) == (False, 'BTC')
    # Space between address
    assert validate_crypto_address_v2('bc1q fggp vs6f rqsj jnnds xsq3 kvqq 66qr 8ztp gv8lt', Currencies.btc) == (
        False, None)
    # Checksum invalid
    assert validate_crypto_address_v2('1PCcFXFAF88GAWFwBJcSVAjZQEDQSEsNi', Currencies.btc) == (False, 'BTC')
    assert validate_crypto_address_v2('1APx5YVAkyhWQe2EnXQkisGju2PR7uY56h', Currencies.btc) == (False, 'BTC')
    assert validate_crypto_address_v2('1PvaArvVPY6BYA6phPYGtAzGsNmFtVzFEL', Currencies.btc) == (False, 'BTC')
    assert validate_crypto_address_v2('3MmPRs4wQQHqHAcsafhnLvHSR8djvzV8Eg', Currencies.btc) == (False, 'BTC')
    # Invalid inputs
    assert validate_crypto_address_v2('بانک صادرات', Currencies.btc) == (False, None)
    assert validate_crypto_address_v2('123456789', Currencies.btc) == (False, None)


@pytest.mark.unit
def test_eth_address_validation_v2():
    # Correct addresses
    # All cap
    assert validate_crypto_address_v2('0x52908400098527886E0F7030069857D2E4169EE7', Currencies.eth) == (True, 'ETH')
    # All lower
    assert validate_crypto_address_v2('0xf53b6ef397a641efb5625b61d67b20189c5f0cd9', Currencies.eth) == (True, 'ETH')
    assert validate_crypto_address_v2('0x0f31e1c9e1a20027e8aac0e89dd29cf12f8b2a20', Currencies.eth) == (True, 'ETH')
    # Normal Addresses
    assert validate_crypto_address_v2('0x00Be17C6aD2738fb20B80f290C8fa1F4F8aB5902', Currencies.eth) == (True, 'ETH')
    assert validate_crypto_address_v2('0x2a1EA66AD4242692d5d6f6fd1dA516EC943E36c1', Currencies.eth) == (True, 'ETH')
    assert validate_crypto_address_v2('0xDD769307d218AD7Ecc05C19Ce2C8bA772F5d66ba', Currencies.eth) == (True, 'ETH')
    assert validate_crypto_address_v2('0x0b877cFA8C9728A632751172f445B1616619a2C8', Currencies.eth) == (True, 'ETH')
    # Incorrect addresses
    # Without 0x
    assert validate_crypto_address_v2('00Be17C6aD2738fb20B80f290C8fa1F4F8aB5902', Currencies.eth) == (False, None)
    # Checksum failed
    assert validate_crypto_address_v2('0x31610423E3Bf10A33daC567d10429AfEa9BC2FfE', Currencies.eth) == (False, 'ETH')
    assert validate_crypto_address_v2('0x00be17C6aD2738fb20B80f290C8fa1F4F8aB5902', Currencies.eth) == (False, 'ETH')


@pytest.mark.unit
def test_ltc_address_validation_v2():
    # Correct addresses
    # Address started with L
    assert validate_crypto_address_v2('LKrLtptzSDV1LGysLRaR2izzvM9sfvTry7', Currencies.ltc) == (True, 'LTC')
    assert validate_crypto_address_v2('LLdE4yUj7WLp3JEf6pStH6KkosTAFuwUSw', Currencies.ltc) == (True, 'LTC')
    # Address started with M
    assert validate_crypto_address_v2('MJ6Qp7KVxdQx5rG7SeHYregU5g9rmvm4af', Currencies.ltc) == (True, 'LTC')
    assert validate_crypto_address_v2('M9Q8FFRRXLpdoAg1zk6xBSD8dfCP2MMLbP', Currencies.ltc) == (True, 'LTC')
    # Segwit addresses
    assert validate_crypto_address_v2('ltc1qq04956j6hfq9qr6f37yr4m3ztujf9d4jgceq9s', Currencies.ltc) == (True, 'LTC')
    assert validate_crypto_address_v2('ltc1ql8hm8kcpxecghr39xgqz6qxsuzgsjel6zha90d', Currencies.ltc) == (True, 'LTC')
    assert validate_crypto_address_v2('ltc1qlz0y4u47lcg5uj7ylw5k28v68zun6prk70gdx7', Currencies.ltc) == (True, 'LTC')
    assert validate_crypto_address_v2('ltc1qtshtgjfmdyf5xnyk07a86vzkc8mxug9ppc3f64', Currencies.ltc) == (True, 'LTC')
    assert validate_crypto_address_v2('ltc1qeu57kxz6s0uqnxp3u9ag9yp22ywuezvq4rnmmj', Currencies.ltc) == (True, 'LTC')
    assert validate_crypto_address_v2('ltc1q5jqsxtxgtqj3w6c83nccgzmjyu20juxl6yt506', Currencies.ltc) == (True, 'LTC')
    # Incorrect addresses
    # Checksum failed
    assert validate_crypto_address_v2('ltc1qlz0y4u47lcg5uj7ylw5k28v68zun6prk70gdx5', Currencies.ltc) == (False, 'LTC')
    # Address with space
    assert validate_crypto_address_v2('ltc1 qlz0y4u47lcg5uj7ylw5k28v68zun6prk70gdx5', Currencies.ltc) == (False, None)
    assert validate_crypto_address_v2('ltc1 qlz0y4 u47lcg 5uj7ylw5k2 8v68zun6prk70gdx5', Currencies.ltc) == (
        False, None)
    # Invalid addresses
    assert validate_crypto_address_v2('LcgkVvMjwZ2Tf9va6K4jNjgrwmxDwpqP15', Currencies.ltc) == (False, 'LTC')
    assert validate_crypto_address_v2('MVY9PRzSzdo1qgu2exX4mNxuioZiTXMtnF', Currencies.ltc) == (False, 'LTC')
    # Deprecated address
    assert validate_crypto_address_v2('3C9iNbpVjV7bjDP5rN95JKSTkCnb8DB6tN', Currencies.ltc) == (False, 'LTC')
    # Testnet addresses
    assert validate_crypto_address_v2('n1wLCQTNYJZGgLbsehQ76HLYomFfnpxXwp', Currencies.ltc) == (False, None)
    assert validate_crypto_address_v2('mutph1tDMUq8ZoJs3dziUGaTumAgKtkgAr', Currencies.ltc) == (False, None)
    assert validate_crypto_address_v2('tltc1qu78xur5xnq6fjy83amy0qcjfau8m367defyhms', Currencies.ltc) == (False, None)


@pytest.mark.unit
def test_usdt_address_validation_v2():
    # Correct addresses
    # ETH
    assert validate_crypto_address_v2('0x9824742b36b2ddf54e67c665b14a8d0095aa5b6e', Currencies.usdt) == (True, 'ETH')
    assert validate_crypto_address_v2('0x0b877cFA8C9728A632751172f445B1616619a2C8', Currencies.usdt) == (True, 'ETH')
    # TRX
    assert validate_crypto_address_v2('TGrc7Je5emcrqcuNfjKBoRgGh36WDzd1xL', Currencies.usdt) == (True, 'TRX')
    # OMNI
    assert validate_crypto_address_v2('1MH5MBtCDx7zQMvjUyV6i5voicXyHQecod', Currencies.usdt) == (True, 'OMNI')
    assert validate_crypto_address_v2('3GTemLwtg2LDRLKMKEFhFWsTvFJj9Zq5LU', Currencies.usdt) == (True, 'OMNI')
    # Incorrect addresses
    assert validate_crypto_address_v2('0x31610423E3Bf10A33daC567d10429AfEa9BC2FfE', Currencies.usdt) == (False, 'ETH')
    assert validate_crypto_address_v2('TGrc7Je5emcrqcuNfjKBoRgGh36WDd1xL', Currencies.trx) == (False, None)
    assert validate_crypto_address_v2('TNNKa5iEcyXkDcQu6XonwPydddFsNynv', Currencies.trx) == (False, None)
    assert validate_crypto_address_v2('TGrc7Je5emcrqcuNfjKBoRgGh36WDzd1wL', Currencies.trx) == (False, 'TRX')
    assert validate_crypto_address_v2('bc1qhhlp9gva56scqmhsr6jfqc9wvtgcyysds3v0vv', Currencies.usdt) == (False, 'OMNI')
    assert validate_crypto_address_v2('1MH5MBtCDx7zQMvjUyV6i5voiccyAQecod', Currencies.usdt) == (False, 'OMNI')


@pytest.mark.unit
def test_xrp_address_validation_v2():
    # Correct addresses
    assert validate_crypto_address_v2('rpHTHXGZddjVWrVDm7zj7bvXfAJ8FWwt8k', Currencies.xrp) == (True, 'XRP')
    assert validate_crypto_address_v2('rEb8TK3gBgk5auZkwc6sHnwrGVJH8DuaLh', Currencies.xrp) == (True, 'XRP')
    assert validate_crypto_address_v2('rLW9gnQo7BQhU6igk5keqYnH3TVrCxGRzm', Currencies.xrp) == (True, 'XRP')
    # Incorrect addresses
    assert validate_crypto_address_v2('rP1afBEfikTz7hIh2ExCDni9W4Bx1dUMRk', Currencies.xrp) == (False, None)
    assert validate_crypto_address_v2('rwRmyGRoJkHKtojaC8SH2wxsnB2q3yNooB', Currencies.xrp) == (False, 'XRP')


@pytest.mark.unit
def test_bch_address_validation_v2():
    # Correct addresses
    assert validate_crypto_address_v2('1CJnEqJEzowE86mzFrjxKAp5BmhCECpeja', Currencies.bch) == (True, 'BCH')
    assert validate_crypto_address_v2('1LTQwgyGb9eWwMshUxeB4n22HZbMhaMwx6', Currencies.bch) == (True, 'BCH')
    assert validate_crypto_address_v2('1LcGngw1cpGQ82ffqzZqPS8A7r2SqUdbHu', Currencies.bch) == (True, 'BCH')
    assert validate_crypto_address_v2('qqalqllag3yqwmqkxj69h34ulxt9sls50yuqwxtzy6', Currencies.bch) == (True, 'BCH')
    assert validate_crypto_address_v2('qr8mxy00llvne2k7mlrmy4es98879ywv9ylcmlnmxg', Currencies.bch) == (True, 'BCH')
    assert validate_crypto_address_v2('14FL8TWn3QEbyTk88dgj8UywuMed3iqjCM', Currencies.bch) == (True, 'BCH')
    assert validate_crypto_address_v2('1J48ZD2kEtuqeAG3qyzS8fBP3JqAJz59L9', Currencies.bch) == (True, 'BCH')
    assert validate_crypto_address_v2('qza3rvtv9rhpsxk88jxqs8v63amcgw6u7vkm6anstd', Currencies.bch) == (True, 'BCH')
    assert validate_crypto_address_v2('qza3rvtv9rhpsxk88jxqs8v63amcgw6u7v6q3xxs4n', Currencies.bch) == (True, 'BCH')
    # Incorrect addresses
    assert validate_crypto_address_v2('simpleledger:qq3eu2e94gr3sxlmueny3wttlyd6xv6qnvyhplwydn', Currencies.bch) == (
        False, None)
    assert validate_crypto_address_v2('bitcoincash:qqrxa0h9jqnc7v4wmj9ysetsp3y7w9l36u8gnnjulq', Currencies.bch) == (
        False, None)
    assert validate_crypto_address_v2('bitcoincash:qq3eu2e94gr3sxlmueny3wttlyd6xv6qnvgv2ymynd', Currencies.bch) == (
        False, None)
    assert validate_crypto_address_v2('1LcGngw1cpGQ82ffqzZqPS8A7r2SqUddHu', Currencies.bch) == (False, 'BCH')
    assert validate_crypto_address_v2('qq3eu2e94gr3sxlmueny3wttlyd6xv6qnv3y5av3cm', Currencies.bch) == (False, 'BCH')
    assert validate_crypto_address_v2('bitcoincash:qq3eu2e94gr3sxlmueny3wttlyd6xv6qnv3y5av3cm', Currencies.bch) == (
        False, None)
    assert validate_crypto_address_v2('simpleledger:qq3eu2e94gr3sxlmueny3wttlyd6xv6qnv3y5av3cm', Currencies.bch) == (
        False, None)


@pytest.mark.slow
def test_bnb_address_validation_v2():
    # Correct addresses
    assert validate_crypto_address_v2('bnb1e5gfm9yt0jvpkyxh6hd2t7x6judmp4usunzg0j', Currencies.bnb) == (True, 'BNB')
    assert validate_crypto_address_v2('bnb1990lfutz0f9wza6rsh36ysfwt9xpctxrll884r', Currencies.bnb) == (True, 'BNB')
    assert validate_crypto_address_v2('bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gtkgf23', Currencies.bnb) == (True, 'BNB')
    assert validate_crypto_address_v2('bnb1wa7g68scff5t0ljg69zypj0e993anywtlfk9cz', Currencies.bnb) == (True, 'BNB')
    # Incorrect addresses
    assert validate_crypto_address_v2('bnb1e5gem9yt1jvpkyxh6hd1t7x6judmp4uqunzgwe', Currencies.bnb) == (False, 'BNB')
    assert validate_crypto_address_v2('bnb1zwayqrmknatqsxag5kw346nclnajcc577hhmzg', Currencies.bnb) == (False, 'BNB')
    assert validate_crypto_address_v2('bnb136ns6lfw4zs5hg4n85vdthaad7hq5m4gpkgf23', Currencies.bnb) == (False, 'BNB')
    assert validate_crypto_address_v2('tbnb1990lfutz0f9wza6rsh36ysfwt9xpctxrll884r', Currencies.bnb) == (False, None)
    assert validate_crypto_address_v2('tbnb1a3qrp4wpqesxfk9pd9tl7udq5rwte3m30de0nc', Currencies.bnb) == (False, None)


@pytest.mark.unit
def test_eos_address_validation_v2():
    # Correct addresses
    assert validate_crypto_address_v2('nobitexeosw1', Currencies.eos) == (True, 'EOS')
    assert validate_crypto_address_v2('binancecleos', Currencies.eos) == (True, 'EOS')
    assert validate_crypto_address_v2('hitbtcpayins', Currencies.eos) == (True, 'EOS')
    assert validate_crypto_address_v2('luckyfish321', Currencies.eos) == (True, 'EOS')
    assert validate_crypto_address_v2('deposit.pro', Currencies.eos) == (True, 'EOS')
    assert validate_crypto_address_v2('binanceeos', Currencies.eos) == (True, 'EOS')
    assert validate_crypto_address_v2('1nobitexeosw', Currencies.eos) == (True, 'EOS')
    # Incorrect addresses
    assert validate_crypto_address_v2('Reza222hasan', Currencies.eos) == (False, None)
    assert validate_crypto_address_v2('bnb1tmljpexn4dm4yrlpl65h32umtppnjkmf5hcs2n', Currencies.eos) == (False, None)


@pytest.mark.unit
def test_xlm_address_validation_v2():
    # Correct addresses
    assert validate_crypto_address_v2('GDY25GPB4E5JKWX7ZWQV6SHVAK4OLKKRGBJZ5X2E3BVW3XKE7XWRZ2PH', Currencies.xlm) == (
        True, 'XLM')
    assert validate_crypto_address_v2('GAHK7EEG2WWHVKDNT4CEQFZGKF2LGDSW2IVM4S5DP42RBW3K6BTODB4A', Currencies.xlm) == (
        True, 'XLM')
    assert validate_crypto_address_v2('GAEI6QWF4KJLL2XLMFHLO5EQZY3GVYRWVTCX3AJQVSUOXXPZWBA7DWVW', Currencies.xlm) == (
        True, 'XLM')
    # Incorrect addresses
    assert validate_crypto_address_v2('GAEI6QWF4KJLL2XLMFHLO5EQZY3GVYRWVTCX3AJQVSUOXXPZWBA7DWVY', Currencies.xlm) == (
        False, 'XLM')
    assert validate_crypto_address_v2('GAHK7EEG2WWH  VKD NT4C EQFZGKF 2LGDSW2IVM4S5DP42RBW3K6BTODB4A',
                                      Currencies.xlm) == (False, None)
    assert validate_crypto_address_v2('GAEI6QWF4KJLQ2XLMFHLO5EQZY3GVYRWVTCX3AJQVSUOXXPZWBA7DWVY', Currencies.xlm) == (
        False, 'XLM')
    assert validate_crypto_address_v2(' AEI6QWF4KJLQ2XLMFHLO5EQZY3GVYRWVTCX3AJQVSUOXXPZWBA7DWVY', Currencies.xlm) == (
        False, None)
    assert validate_crypto_address_v2('XGAEI6QWF4KJLQ2XLMFHLO5EQZY3GVYRWVTCX3AJQVSUOXXPZWBA7DWVY', Currencies.xlm) == (
        False, None)
    assert validate_crypto_address_v2('AEI6QWF4KJLQ2XLMFHLO5EQZY3GVYRWVTCX3AJQVSUOXXPZWBA7DWVY', Currencies.xlm) == (
        False, None)


@pytest.mark.unit
def test_trx_address_validation_v2():
    assert validate_crypto_address_v2('TGrc7Je5emcrqcuNfjKBoRgGh36WDzd1xL', Currencies.trx) == (True, 'TRX')
    assert validate_crypto_address_v2('TNNKa5iEcyXkDcQu6XonwPydddFsNynvGG', Currencies.trx) == (True, 'TRX')
    assert validate_crypto_address_v2('TGrc7Je5emcrqcuNfjKBoRgGh36WDd1xL', Currencies.trx) == (False, None)
    assert validate_crypto_address_v2('TNNKa5iEcyXkDcQu6XonwPydddFsNynvGc', Currencies.trx) == (False, 'TRX')


@pytest.mark.unit
def test_dot_address_validation_v2():
    # DOT
    # Correct addresses
    assert validate_crypto_address_v2('13ALHq3vrN9Mwx3UzZnbon2oA33TfM9nepPNZQ1yWnfyUqer', Currencies.dot) == (
        True, 'DOT')
    # Incorrect addresses
    assert validate_crypto_address_v2('5EcQKVbvPRaJ8kvhxgTcqUnmcbX2HjqMm7JXQ7WifK1xHpKA', Currencies.dot) == (
        False, None)
    assert validate_crypto_address_v2('13ALHq3vrN9Mwx3UzZnbon2oA33TfM9nepPNZQ1yWnfyUqes', Currencies.dot) == (
        False, 'DOT')
    assert validate_crypto_address_v2('13ALHq3vrN9Mwx3UzZnbon2oA33TfM9nepPNZQ1yWnfyU', Currencies.dot) == (False, 'DOT')
    assert validate_crypto_address_v2('23ALHq3vrN9Mwx3UzZnbon2oA33TfM9nepPNZQ1yWnfyUqes', Currencies.dot) == (
        False, None)


@pytest.mark.unit
def test_ada_address_validation_v2():
    # ADA
    # Correct addresses
    assert validate_crypto_address_v2(
        'addr1qxqs59lphg8g6qndelq8xwqn60ag3aeyfcp33c2kdp46a09re5df3pzwwmyq946axfcejy5n4x0y99wqpgtp2gd0k09qsgy6pz',
        Currencies.ada) == (True, 'ADA')
    assert validate_crypto_address_v2('addr1vxw96rx9arvgem7vhdgv3a9u8na07nynhyj7wfn3w96rtggvzfqeq', Currencies.ada) == (
        True, 'ADA')
    assert validate_crypto_address_v2('addr1v8v3auqmw0eszza3ww29ea2pwftuqrqqyu26zvzjq9dt2ncydzvs5', Currencies.ada) == (
        True, 'ADA')
    assert validate_crypto_address_v2(
        'addr1qy9zqj47wzuquzn90w7hyy72gwzgnnea8gn4xyumplyeg5w8xcp8lda6wtjw9mfvqrpvkhpfj3ttp83tfqtl0f3wrj2qzr39jf',
        Currencies.ada) == (True, 'ADA')
    assert validate_crypto_address_v2(
        'addr1q8m5asyuttv7n83vzdm6zaxzguszex0lqeygg8rekuzwu0k8xcp8lda6wtjw9mfvqrpvkhpfj3ttp83tfqtl0f3wrj2qjl5shp',
        Currencies.ada) == (True, 'ADA')
    assert validate_crypto_address_v2(
        'addr1q80tw7ltwly4rv95urntqx4p3pyl0vgeurt2ntverdv48ve4yephjk97t6qnqncgcrk6sfrf9449u3tcg8wlk6dtt7jsqna6gj',
        Currencies.ada) == (True, 'ADA')
    # Incorrect addresses
    assert validate_crypto_address_v2(
        'addr1qxqs59lphg8g6qndelq8xwqn60ag3aeyfcp33c2kdp46a09re5df3pzwwmyq946axfcejy5n4x0y99wqpgtp2gd0k09qsgy6pt',
        Currencies.ada) == (False, 'ADA')
    assert validate_crypto_address_v2(
        'addrqxqs59lphg8g6qndelq8xwqn60ag3aeyfcp33c2kdp46a09re5df3pzwwmyq946axfcejy5n4x0y99wqpgtp2gd0k09qsgy6pz',
        Currencies.ada) == (False, 'ADA')
    assert validate_crypto_address_v2(
        'addr1qxqs59lphg8g6qndelq8xwqn60ag3aeyfcp33c2kdp46a09re5df3pzwwmyq946axfcejy5n4x0y99wqpgtp2gd0k09',
        Currencies.ada) == (False, 'ADA')


@pytest.mark.unit
def test_validate_tag():
    from importlib.util import find_spec
    try:
        find_spec('exchange.wallet.models')
    except ModuleNotFoundError:
        return
    assert validate_tag('33213', Currencies.xrp)
    assert not validate_tag('1memo', Currencies.xrp)
    assert not validate_tag('0', Currencies.xrp)


@pytest.mark.unit
def test_memo_validation_v2():
    # Persian
    assert validate_memo_v2('ندارد', Currencies.eos) is False
    assert validate_memo_v2('ندارد', Currencies.xlm) is False
    assert validate_memo_v2('ندارد', Currencies.bnb) is False
    assert validate_memo_v2('ندارد', Currencies.xrp) is False

    # Space
    assert validate_memo_v2('12 3  ', Currencies.eos) is False
    assert validate_memo_v2('12 3  ', Currencies.xlm) is False
    assert validate_memo_v2('12 3  ', Currencies.bnb) is False
    assert validate_memo_v2('12 3  ', Currencies.xrp) is False

    # Non-integer
    assert validate_memo_v2('1memo', Currencies.eos) is True
    assert validate_memo_v2('1memo', Currencies.xlm) is True
    assert validate_memo_v2('1memo', Currencies.bnb) is True
    assert validate_memo_v2('1memo', Currencies.xrp) is False

    # Zero
    assert validate_memo_v2('0', Currencies.eos) is True
    assert validate_memo_v2('0', Currencies.xlm) is True
    assert validate_memo_v2('0', Currencies.bnb) is True
    assert validate_memo_v2('0', Currencies.xrp) is False


@pytest.mark.unit
def test_tezos_address_validation():
    assert validate_crypto_address('tz1QWad59nCK6BSnoWsCp97HSr6qRtBVrgaJ', Currencies.xtz, 'XTZ')
    assert validate_crypto_address('tz1XEJBiCZfBbo8rWNcQfABVb2dRGG5Kp9vB', Currencies.xtz, 'XTZ')
    assert validate_crypto_address('tz1Q7RpsRvbozbY5zuhv5AaXuoqeXrcFAtgF', Currencies.xtz, 'XTZ')
    assert validate_crypto_address('tz2WDATNYnp7FdsmuZDYSidioZqeoLNZqXvE', Currencies.xtz, 'XTZ')
    assert validate_crypto_address('tz2FqBRA1yPQLo4JXfMCT1dFWbFpFE4Tq3bm', Currencies.xtz, 'XTZ')
    assert validate_crypto_address('tz3YJYNkKUktLkJXoWLyo3r6dTwfwGASVzUx', Currencies.xtz, 'XTZ')
    assert validate_crypto_address('tz3e7LbZvUtoXhpUD1yb6wuFodZpfYRb9nWJ', Currencies.xtz, 'XTZ')
    assert not validate_crypto_address('YJYNkKUktLkJXoWLyo3r6dTwfwGASVzUX', Currencies.xtz, 'XTZ')
    assert not validate_crypto_address('XEJBiCZfBbo8rWNcQfABVb2dRGG5Kp9vB', Currencies.xtz, 'XTZ')
    assert not validate_crypto_address('FqBRA1yPQLo4JXfMCT1dFWbFpFE4Tq3bm', Currencies.xtz, 'XTZ')
    assert not validate_crypto_address('tz1QWad59nCK6BSnoWsCp97HSr6qRtBVrgao', Currencies.xtz, 'XTZ')
    assert not validate_crypto_address('tz2WDATNYnp7FdsmuZDYSidioZqeoLNZqXve', Currencies.xtz, 'XTZ')
    assert not validate_crypto_address('tz3YJYNkKUktLkJXoWLyo3r6dTwfwGASVzUX', Currencies.xtz, 'XTZ')
    assert not validate_crypto_address('tzXEJBiCZfBbo8rWNcQfABVb2dRGG5Kp9vB', Currencies.xtz, 'XTZ')
    assert not validate_crypto_address('tzWDATNYnp7FdsmuZDYSidioZqeoLNZqXvE', Currencies.xtz, 'XTZ')
    assert not validate_crypto_address('tzYJYNkKUktLkJXoWLyo3r6dTwfwGASVzUx', Currencies.xtz, 'XTZ')
    assert not validate_crypto_address('KT1PWx2mnDueood7fEmfbBDKx1D9BAnnXitn', Currencies.xtz, 'XTZ')
    assert not validate_crypto_address('KT1CoTu4CXcWoVk69Ukbgwx2iDK7ZA4FMSpJ', Currencies.xtz, 'XTZ')
    assert not validate_crypto_address('KT1CoTu4gwx2iDK7ZA4FMSpJ', Currencies.xtz, 'XTZ')
    assert not validate_crypto_address('tzXEJBiCZfBbo8rWGG5Kp9vB', Currencies.xtz, 'XTZ')


@pytest.mark.unit
def test_enjin_address_validation():
    # We just validate 'en' addresses not even dot addresses which indicate the en address itself
    assert validate_crypto_address('enCWBh9GZ1x8cz6oqNzLPhaYmFC3rENSfYsJxk2QJ2jXtLfPK', Currencies.enj, 'ENJ')
    assert validate_crypto_address('enD9wdMEaQa3LR6AUWQv5Csyg4aNVd2wHeMS5NNEFBjrSRTzj', Currencies.enj, 'ENJ')
    assert not validate_crypto_address('12pjNmNmCsuRB4tmXHgoUcMAZfkWym2dDbjgEKSS9Box5PiH', Currencies.enj, 'ENJ')
    assert not validate_crypto_address('13UVJyLnbVp8c4FQeiGUyun5P45ANRXFK5rnrfGPJC8WAQhT', Currencies.enj, 'ENJ')
    assert not validate_crypto_address('efQRu88oyqs5TZZBXsnUGt88kMkR727wpiSRV3MnLwek8uzDn', Currencies.enj, 'ENJ')
    assert not validate_crypto_address('0x50a36a5110fe0c5419a4d866b73871177c3a4681752b782c20a300b187370e49', Currencies.enj, 'ENJ')

