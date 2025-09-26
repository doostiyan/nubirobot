from decimal import Decimal
from typing import Optional

from flask import request, abort, Response

CURRENCIES = {
    'usd': 1, 'rls': 2, 'irt': 2, 'irr': 2,
    'btc': 10, 'eth': 11, 'ltc': 12, 'usdt': 13, 'xrp': 14, 'bch': 15, 'bnb': 16, 'eos': 17, 'doge': 18, 'xlm': 19,
    'trx': 20, 'ada': 21, 'xmr': 22, 'xem': 23, 'iota': 24, 'etc': 25, 'dash': 26, 'zec': 27, 'neo': 28, 'qtum': 29,
    'xtz': 30, 'pmn': 31, 'link': 32, 'dai': 33, 'dot': 34, 'uni': 35, 'aave': 36, 'sol': 37, 'pol': 38, 'fil': 39,
    'grt': 40, 'theta': 41, 'shib': 42,
    '1inch': 50, 'alice': 51, 'alpha': 52, 'ankr': 53, 'arpa': 54, 'ata': 55, 'atom': 56, 'avax': 57, 'axs': 58, 'bake': 59,
    'bal': 60, 'band': 61, 'bat': 62, 'bel': 63, 'blz': 64, '1m_btt': 65, 'c98': 66, 'celr': 67, 'chr': 68, 'comp': 69,
    'coti': 70, 'ctk': 71, 'ctsi': 72, 'dodo': 73, 'egld': 74, 'ftm': 75, 'gala': 76, 'iotx': 77, 'knc': 78, 'ksm': 79,
    'lina': 80, 'lit': 81, 'mask': 82, 'mkr': 83, 'near': 84, 'ocean': 85, 'ont': 86, 'reef': 87, 'sfp': 88, 'snx': 89,
    'sushi': 90, 'sxp': 91, 'tlm': 92, 'unfi': 93, 'yfi': 94, 'yfii': 95, 'zil': 96, 'mana': 97, 'sand': 98, 'ape': 99,
    'one': 100, 'wbtc': 101, 'usdc': 102, 'algo': 103, 'luna': 104, 'klay': 105, 'gmt': 106, 'chz': 107, 'vet': 108, 'qnt': 109,
    'busd': 110, 'flow': 111, 'hbar': 112, 'pgala': 113, 'egala': 114, 'enj': 115, 'op': 116, 'crv': 117, 'cake': 118, 'ldo': 119,
    'dydx': 120, 'gno': 121, 'apt': 122, 'flr': 123, 'lrc': 124, 'ens': 125, 'lpt': 126, 'glm': 127, 'api3': 128, 'elf': 129,
    'dao': 130, 'cvc': 131, 'nmr': 132, 'storj': 133, 'cvx': 134, 'snt': 135, 'slp': 136, '1m_nft': 137, 'srm': 138, 'ant': 139,
    'ilv': 140, 't': 141, 'icp': 142, 'hnt': 143, '1b_babydoge': 144, 'ton': 145, '100k_floki': 146, 'zrx': 147, 'imx': 148,
    'mdt': 149, 'blur': 150, 'magic': 151, 'arb': 152, 'rpl': 153, 'paxg': 154,'gmx': 155, 'weth': 157, 'ssv': 158, 'wld': 159,
    'omg': 160, 'agld': 161, 'rdnt': 162, 'jst': 163, 'render': 164, 'bico': 165, 'woo': 166, 'skl': 167, 'fet': 168,
    'gal': 169, 'agix': 170, 'waxp': 171, 'trb': 172, 'rsr': 173, 'ygg': 174, 'auction': 175, 'meme': 176, 'uma': 177,
    'bigtime': 178, 'id': 179, 'orbs': 180, 'perp': 181, 'bnt': 182, 'gods': 183, 'looks': 184, 'badger': 185,
    'ren': 186, 'vra': 187, 'front': 188, 'ethfi': 189, 'not': 190, '1m_pepe': 191,
    'om': 192, 'aevo': 193, 'w': 194, 'zro': 195, 'g': 196, 'ondo': 197, 'dogs': 198, 'cati': 199, 'hmstr': 200, 'xaut': 201, 'eigen': 202,
    'jasmy': 203, 'ena': 204, 'pendle': 205, 'bnx': 206, 'super': 207, 'hot': 208,
    'edu': 209, 'safe': 210, 'fxs': 211, 'wsdm': 212, 'twt': 213, 'x': 214, 'banana':215, 'major': 216, 'move': 217,
    'strk': 218, 'metis': 219, 'inj': 220, 'turbo': 221, 'dexe': 222, 'zkj': 223, 'ath': 224, 'cookie': 225, 'cgpt': 226, 's': 227,
    'neiro': 228, '1k_bonk': 229, 'morpho': 230, '1k_cat': 231, 'nexo': 232, 'amp': 233, 'cfx': 234, 'alt': 235, 'axl': 236,
    'form': 237, 'pha': 238, 'zent': 239, 'iq': 240, 'usual': 241, 'wif': 243, 'ray': 244, 'tnsr': 245,
    'vine': 246, 'act': 247, 'goat': 248, 'anime': 249, 'stg': 250, 'cow': 251, 'people': 252, 'powr': 253, 'ach': 254, 'xai': 255,
    'aixbt': 256, 'virtual':257, 'kaito': 258,
}
ID_TO_CURRENCY_MAPPER = {value: key for key, value in CURRENCIES.items()}

# TODO: This is copied from app-config and should be changed to read from app-config ASAP!
CURRENCIES_WITHOUT_MARKET = {
    52, 76, 78, 88, 110, 113, 123, 140, 153, 157, 171, 174, 175, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188,
    211, 213, 238, 239, 240, 241, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255
}
AVAILABLE_CRYPTO_CURRENCIES = {
    10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 25, 27, 30, 31,
    32, 33, 34, 35, 36, 37, 38, 39, 40, 42, 50, 53, 56, 57, 58, 60, 61, 62, 65, 67, 69, 74, 75, 76, 77, 82, 83, 84, 89,
    90, 94, 96, 97, 98, 99, 100, 101, 102, 103, 106, 107, 109, 110, 111, 112, 113,
    114, 115, 117, 118, 119, 120, 122, 124, 125, 126, 127, 128, 130, 131, 132, 133, 134, 135, 136, 137, 141, 144, 145,
    146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 158, 159, 160, 161, 162, 163, 164, 165, 166, 167, 168, 172, 173, 176,
    177, 178, 189, 190, 191, 192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207, 208, 209, 210,
    214, 215, 216, 217, 218, 219, 220, 221, 222, 223, 224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236,
    237, 238, 239, 240, 241, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255, 256, 257, 258
}
AVAILABLE_CRYPTO_CURRENCIES -= CURRENCIES_WITHOUT_MARKET

VALID_MARKET_SYMBOLS = set()
for i_id in AVAILABLE_CRYPTO_CURRENCIES:
    currency_name = ID_TO_CURRENCY_MAPPER.get(i_id)
    VALID_MARKET_SYMBOLS.add(f'{currency_name.upper()}IRT')
    VALID_MARKET_SYMBOLS.add(f'{currency_name.upper()}USDT')
VALID_MARKET_SYMBOLS.discard("USDTUSDT")
VALID_MARKET_SYMBOLS.discard("PMNIRT")

PRICE_PRECISIONS = {
    'BTCIRT': Decimal('1e1'), 'BTCUSDT': Decimal('1e-2'),
    'ETHIRT': Decimal('1e1'), 'ETHUSDT': Decimal('1e-2'),
    'LTCIRT': Decimal('1e1'), 'LTCUSDT': Decimal('1e-2'),
    'XRPIRT': Decimal('1e1'), 'XRPUSDT': Decimal('1e-5'),
    'BCHIRT': Decimal('1e1'), 'BCHUSDT': Decimal('1e-2'),
    'USDTIRT': Decimal('1e1'),
    'BNBIRT': Decimal('1e1'), 'BNBUSDT': Decimal('1e-4'),
    'EOSIRT': Decimal('1e1'), 'EOSUSDT': Decimal('1e-4'),
    'XLMIRT': Decimal('1e1'), 'XLMUSDT': Decimal('1e-5'),
    'ETCIRT': Decimal('1e1'), 'ETCUSDT': Decimal('1e-4'),
    'TRXIRT': Decimal('1e1'), 'TRXUSDT': Decimal('1e-5'),
    'PMNIRT': Decimal('1e1'), 'PMNUSDT': Decimal('1e-5'),
    'DOGEIRT': Decimal('1'), 'DOGEUSDT': Decimal('1e-7'),
    'ADAIRT': Decimal('1e1'), 'ADAUSDT': Decimal('1e-4'),
    'LINKIRT': Decimal('1e1'), 'LINKUSDT': Decimal('1e-3'),
    'DAIIRT': Decimal('1e1'), 'DAIUSDT': Decimal('1e-4'),
    'DOTIRT': Decimal('1e1'), 'DOTUSDT': Decimal('1e-3'),
    'UNIIRT': Decimal('1e1'), 'UNIUSDT': Decimal('1e-3'),
    'AAVEIRT': Decimal('1e1'), 'AAVEUSDT': Decimal('1e-2'),
    'GRTIRT': Decimal('1e1'), 'GRTUSDT': Decimal('1e-5'),
    'SHIBIRT': Decimal('1'), 'SHIBUSDT': Decimal('1e-5'),
    'FILIRT': Decimal('1e1'), 'FILUSDT': Decimal('1e-3'),
    'POLIRT': Decimal('1e1'), 'POLUSDT': Decimal('1e-4'),
    'SOLIRT': Decimal('1e1'), 'SOLUSDT': Decimal('1e-3'),
    'THETAIRT': Decimal('1e1'), 'THETAUSDT': Decimal('1e-3'),
    'AVAXIRT': Decimal('1e1'), 'AVAXUSDT': Decimal('1e-3'),
    'FTMIRT': Decimal('1e1'), 'FTMUSDT': Decimal('1e-4'),
    'MKRIRT': Decimal('1e1'), 'MKRUSDT': Decimal('1e-2'),
    'AXSIRT': Decimal('1e1'), 'AXSUSDT': Decimal('1e-2'),
    'MANAIRT': Decimal('1e1'), 'MANAUSDT': Decimal('1e-4'),
    'SANDIRT': Decimal('1e1'), 'SANDUSDT': Decimal('1e-4'),
    'APEIRT': Decimal('1e1'), 'APEUSDT': Decimal('1e-3'),
    'ONEIRT': Decimal('1e1'), 'ONEUSDT': Decimal('1e-5'),
    'GMTIRT': Decimal('1e1'), 'GMTUSDT': Decimal('1e-4'),
    'WBTCIRT': Decimal('1e1'), 'WBTCUSDT': Decimal('1e-1'),
    'USDCIRT': Decimal('1e1'), 'USDCUSDT': Decimal('1e-4'),
    'NEARIRT': Decimal('1e1'), 'NEARUSDT': Decimal('1e-3'),
    'ATOMIRT': Decimal('1e1'), 'ATOMUSDT': Decimal('1e-3'),
    'BATIRT': Decimal('1e1'), 'BATUSDT': Decimal('1e-4'),
    'CHZIRT': Decimal('1e1'), 'CHZUSDT': Decimal('1e-5'),
    'QNTIRT': Decimal('1e1'), 'QNTUSDT': Decimal('1e-1'),
    'XMRIRT': Decimal('1e1'), 'XMRUSDT': Decimal('1e-2'),
    'ALGOIRT': Decimal('1e1'), 'ALGOUSDT': Decimal('1e-4'),
    'GALAIRT': Decimal('1e1'), 'GALAUSDT': Decimal('1e-5'),
    'BUSDIRT': Decimal('1e1'), 'BUSDUSDT': Decimal('1e-4'),
    'HBARIRT': Decimal('1e1'), 'HBARUSDT': Decimal('1e-5'),
    'PGALAIRT': Decimal('1e1'), 'PGALAUSDT': Decimal('1e-5'),
    'EGALAIRT': Decimal('1e1'), 'EGALAUSDT': Decimal('1e-5'),
    'FLOWIRT': Decimal('1e1'), 'FLOWUSDT': Decimal('1e-3'),
    'YFIIRT': Decimal('1e1'), 'YFIUSDT': Decimal('1'),
    '1INCHIRT': Decimal('1e1'), '1INCHUSDT': Decimal('1e-4'),
    'SNXIRT': Decimal('1e1'), 'SNXUSDT': Decimal('1e-3'),
    'CRVIRT': Decimal('1e1'), 'CRVUSDT': Decimal('1e-3'),
    'ENJIRT': Decimal('1e1'), 'ENJUSDT': Decimal('1e-4'),
    'LDOIRT': Decimal('1e1'), 'LDOUSDT': Decimal('1e-4'),
    'ANKRIRT': Decimal('1e1'), 'ANKRUSDT': Decimal('1e-5'),
    'DYDXIRT': Decimal('1e1'), 'DYDXUSDT': Decimal('1e-3'),
    'APTIRT': Decimal('1e1'), 'APTUSDT': Decimal('1e-4'),
    'MASKIRT': Decimal('1e1'), 'MASKUSDT': Decimal('1e-3'),
    'FLRIRT': Decimal('1e1'), 'FLRUSDT': Decimal('1e-5'),
    'LRCIRT': Decimal('1e1'), 'LRCUSDT': Decimal('1e-4'),
    'COMPIRT': Decimal('1e1'), 'COMPUSDT': Decimal('1e-2'),
    'BALIRT': Decimal('1e1'), 'BALUSDT': Decimal('1e-3'),
    'ENSIRT': Decimal('1e1'), 'ENSUSDT': Decimal('1e-2'),
    'SUSHIIRT': Decimal('1e1'), 'SUSHIUSDT': Decimal('1e-3'),
    'LPTIRT': Decimal('1e1'), 'LPTUSDT': Decimal('1e-2'),
    'GLMIRT': Decimal('1e1'), 'GLMUSDT': Decimal('1e-4'),
    'API3IRT': Decimal('1e1'), 'API3USDT': Decimal('1e-3'),
    'AELFIRT': Decimal('1e1'), 'AELFUSDT': Decimal('1e-4'),
    'DAOIRT': Decimal('1e1'), 'DAOUSDT': Decimal('1e-3'),
    'CVCIRT': Decimal('1e1'), 'CVCUSDT': Decimal('1e-4'),
    'NMRIRT': Decimal('1e1'), 'NMRUSDT': Decimal('1e-2'),
    'STORJIRT': Decimal('1e1'), 'STORJUSDT': Decimal('1e-4'),
    'CVXIRT': Decimal('1e1'), 'CVXUSDT': Decimal('1e-3'),
    'EGLDIRT': Decimal('1e1'), 'EGLDUSDT': Decimal('1e-2'),
    'SNTIRT': Decimal('1e1'), 'SNTUSDT': Decimal('1e-5'),
    'SLPIRT': Decimal('1'), 'SLPUSDT': Decimal('1e-6'),
    'HNTIRT': Decimal('1e1'), 'HNTUSDT': Decimal('1e-4'),
    'SRMIRT': Decimal('1e1'), 'SRMUSDT': Decimal('1e-3'),
    'ANTIRT': Decimal('1e1'), 'ANTUSDT': Decimal('1e-3'),
    'ILVIRT': Decimal('1e1'), 'ILVUSDT': Decimal('1e-1'),
    'ZRXIRT': Decimal('1e1'), 'ZRXUSDT': Decimal('1e-4'),
    'IMXIRT': Decimal('1e1'), 'IMXUSDT': Decimal('1e-3'),
    '100K_FLOKIIRT': Decimal('1'), '100K_FLOKIUSDT': Decimal('1e-4'),
    '1B_BABYDOGEIRT': Decimal('1e1'), '1B_BABYDOGEUSDT': Decimal('1e-3'),
    'BLURIRT': Decimal('1e1'), 'BLURUSDT': Decimal('1e-4'),
    '1M_NFTIRT': Decimal('1e1'), '1M_NFTUSDT': Decimal('1e-4'),
    '1M_BTTIRT': Decimal('1e1'), '1M_BTTUSDT': Decimal('1e-3'),
    'TIRT': Decimal('1e1'), 'TUSDT': Decimal('1e-4'),
    'CELRIRT': Decimal('1e1'), 'CELRUSDT': Decimal('1e-5'),
    'ARBIRT': Decimal('1e1'), 'ARBUSDT': Decimal('1e-4'),
    'TONIRT': Decimal('1e1'), 'TONUSDT': Decimal('1e-3'),
    'MAGICIRT': Decimal('1e1'), 'MAGICUSDT': Decimal('1e-4'),
    'GMXIRT': Decimal('1e1'), 'GMXUSDT': Decimal('1e-2'),
    'BANDIRT': Decimal('1e1'), 'BANDUSDT': Decimal('1e-3'),
    'MDTIRT': Decimal('1e1'), 'MDTUSDT': Decimal('1e-5'),
    'SSVIRT': Decimal('1e1'), 'SSVUSDT': Decimal('1e-2'),
    'WLDIRT': Decimal('1e1'), 'WLDUSDT': Decimal('1e-4'),
    'OMGIRT': Decimal('1e1'), 'OMGUSDT': Decimal('1e-4'),
    'RDNTIRT': Decimal('1e1'), 'RDNTUSDT': Decimal('1e-4'),
    'JSTIRT': Decimal('1e1'), 'JSTUSDT': Decimal('1e-5'),
    'RENDERIRT': Decimal('1e1'), 'RENDERUSDT': Decimal('1e-3'),
    'XTZIRT': Decimal('1e1'), 'XTZUSDT': Decimal('1e-3'),
    'BICOIRT': Decimal('1e1'), 'BICOUSDT': Decimal('1e-4'),
    'WOOIRT': Decimal('1e1'), 'WOOUSDT': Decimal('1e-5'),
    'SKLIRT': Decimal('1e1'), 'SKLUSDT': Decimal('1e-5'),
    'GALIRT': Decimal('1e1'), 'GALUSDT': Decimal('1e-4'),
    'FETIRT': Decimal('1e1'), 'FETUSDT': Decimal('1e-4'),
    'AGIXIRT': Decimal('1e1'), 'AGIXUSDT': Decimal('1e-4'),
    'AGLDIRT': Decimal('1e1'), 'AGLDUSDT': Decimal('1e-4'),
    'TRBIRT': Decimal('1e1'), 'TRBUSDT': Decimal('1e-2'),
    'RSRIRT': Decimal('1'), 'RSRUSDT': Decimal('1e-6'),
    'ETHFIIRT': Decimal('1e1'), 'ETHFIUSDT': Decimal('1e-3'),
    'NOTIRT': Decimal('1e1'), 'NOTUSDT': Decimal('1e-6'),
    '1M_PEPEIRT': Decimal('1e1'), '1M_PEPEUSDT': Decimal('1e-4'),
    'OMIRT': Decimal('1e1'), 'OMUSDT': Decimal('1e-4'),
    'AEVOIRT': Decimal('1e1'), 'AEVOUSDT': Decimal('1e-4'),
    'WIRT': Decimal('1e1'), 'WUSDT': Decimal('1e-4'),
    'ZROIRT': Decimal('1e1'), 'ZROUSDT': Decimal('1e-3'),
    'UMAIRT': Decimal('1e1'), 'UMAUSDT': Decimal('1e-3'),
    'MEMEIRT': Decimal('1e1'), 'MEMEUSDT': Decimal('1e-5'),
    'GIRT': Decimal('1e1'), 'GUSDT': Decimal('1e-5'),
    'ONDOIRT': Decimal('1e1'), 'ONDOUSDT': Decimal('1e-4'),
    'DOGSIRT': Decimal('1'), 'DOGSUSDT': Decimal('1e-7'),
    'CATIIRT': Decimal('1e1'), 'CATIUSDT': Decimal('1e-4'),
    'HMSTRIRT': Decimal('1e1'), 'HMSTRUSDT': Decimal('1e-6'),
    'PAXGIRT': Decimal('1e1'), 'PAXGUSDT': Decimal('1'),
    'XAUTIRT': Decimal('1e1'), 'XAUTUSDT': Decimal('1e-1'),
    'EIGENIRT': Decimal('1e1'), 'EIGENUSDT': Decimal('1e-3'),
    'ENAIRT': Decimal('1e1'), 'ENAUSDT': Decimal('1e-4'),
    'PENDLEIRT': Decimal('1e1'), 'PENDLEUSDT': Decimal('1e-3'),
    'JASMYIRT': Decimal('1e1'), 'JASMYUSDT': Decimal('1e-6'),
    'SUPERIRT': Decimal('1e1'), 'SUPERUSDT': Decimal('1e-4'),
    'BNXIRT': Decimal('1e1'), 'BNXUSDT': Decimal('1e-4'),
    'CAKEIRT': Decimal('1e1'), 'CAKEUSDT': Decimal('1e-4'),
    'HOTIRT': Decimal('1'), 'HOTUSDT': Decimal('1e-6'),
    'EDUIRT': Decimal('1e1'), 'EDUUSDT': Decimal('1e-4'),
    'SAFEIRT': Decimal('1e1'), 'SAFEUSDT': Decimal('1e-4'),
    'XIRT': Decimal('1e-2'), 'XUSDT': Decimal('1e-7'),
    'BANANAIRT': Decimal('1e1'), 'BANANAUSDT': Decimal('1e-2'),
    'MAJORIRT': Decimal('1e1'), 'MAJORUSDT': Decimal('1e-6'),
    'MOVEIRT': Decimal('1e1'), 'MOVEUSDT': Decimal('1e-5'),
    'STRKIRT': Decimal('1e1'), 'STRKUSDT': Decimal('1e-4'),
    'METISIRT': Decimal('1e1'), 'METISUSDT': Decimal('1e-2'),
    'ZILIRT': Decimal('1e1'), 'ZILUSDT': Decimal('1e-5'),
    'INJIRT': Decimal('1e1'), 'INJUSDT': Decimal('1e-3'),
    'ZECIRT': Decimal('1e1'), 'ZECUSDT': Decimal('1e-2'),
    'TURBOIRT': Decimal('1'), 'TURBOUSDT': Decimal('1e-7'),
    'DEXEIRT': Decimal('1e1'), 'DEXEUSDT': Decimal('1e-3'),
    'ZKJIRT': Decimal('1e1'), 'ZKJUSDT': Decimal('1e-4'),
    'ATHIRT': Decimal('1e1'), 'ATHUSDT': Decimal('1e-5'),
    'COOKIEIRT': Decimal('1e1'), 'COOKIEUSDT': Decimal('1e-4'),
    'CGPTIRT': Decimal('1e1'), 'CGPTUSDT': Decimal('1e-5'),
    'SIRT': Decimal('1e1'), 'SUSDT': Decimal('1e-4'),
    'NEIROIRT': Decimal('1e-3'), 'NEIROUSDT': Decimal('1e-8'),
    '1K_BONKIRT': Decimal('1e-3'), '1K_BONKUSDT': Decimal('1e-6'),
    'MORPHOIRT': Decimal('1e1'), 'MORPHOUSDT': Decimal('1e-4'),
    'IOTXIRT': Decimal('1e1'), 'IOTXUSDT': Decimal('1e-5'),
    '1K_CATIRT': Decimal('1e-1'), '1K_CATUSDT': Decimal('1e-5'),
    'NEXOIRT': Decimal('1e1'), 'NEXOUSDT': Decimal('1e-3'),
    'AMPIRT': Decimal('1e1'), 'AMPUSDT': Decimal('1e-6'),
    'CFXIRT': Decimal('1e1'), 'CFXUSDT': Decimal('1e-5'),
    'ALTIRT': Decimal('1e1'), 'ALTUSDT': Decimal('1e-5'),
    'AXLIRT': Decimal('1e1'), 'AXLUSDT': Decimal('1e-4'),
    'FORMIRT': Decimal('1e1'), 'FORMUSDT': Decimal('1e-4'),
    'WIFIRT': Decimal('1e1'), 'WIFUSDT': Decimal('1e-4'),
    'RAYIRT': Decimal('1e1'), 'RAYUSDT': Decimal('1e-4'),
    'TNSRIRT': Decimal('1e1'), 'TNSRUSDT': Decimal('1e-4'),
    'AIXBTIRT': Decimal('1e1'), 'AIXBTUSDT': Decimal('1e-5'),
    'VIRTUALIRT': Decimal('1e1'), 'VIRTUALUSDT': Decimal('1e-4'),
    'KAITOIRT': Decimal('1e1'), 'KAITOUSDT': Decimal('1e-4'),

}


def get_data():
    if request.method == 'GET':
        return request.args
    if request.is_json:
        return request.get_json()
    return request.form


def called_from_frontend():
    frontend_url = 'https://nobitex.ir'
    referer = request.headers.get('Referer', '')
    return referer.startswith(frontend_url)


def create_response(response, status=200, mimetype='application/json', max_age=None, cors=False):
    response = Response(
        response=response,
        status=status,
        mimetype=mimetype,
    )
    if max_age:
        response.headers['Cache-Control'] = 'max-age={}'.format(max_age)
    if cors:
        if isinstance(cors, bool):
            cors = '*'
        response.headers['Access-Control-Allow-Origin'] = str(cors)
    return response


def error(code: str, message: str, status: int = 400):
    abort(Response(
        response=f'{{"status": "failed", "code": "{code}", "message": "{message}"}}',
        status=status,
        mimetype='application/json'
    ))


def parse_int(s: Optional[str], required: bool = False, **_) -> Optional[int]:
    if not s:
        if required:
            abort(400)
        return None
    s = str(s)
    try:
        return int(s)
    except ValueError:
        abort(400)


def parse_symbol(symbol: Optional[str]) -> str:
    if symbol not in VALID_MARKET_SYMBOLS:
        error("InvalidSymbol", f"The symbol \\\"{symbol}\\\" is not a valid market pair.")
    return symbol


def parse_currency(s: Optional[str]) -> int:
    currency = CURRENCIES.get((s or '').lower())
    if currency is None:
        error("InvalidCurrency", f"The symbol \\\"{s}\\\" is not a valid currency.")
    return currency
