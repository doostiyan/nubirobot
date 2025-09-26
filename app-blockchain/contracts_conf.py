from exchange.blockchain.models import get_token_code, CurrenciesNetworkName

ERC20_contract_info = {
    'mainnet': {
        get_token_code('inch', 'erc20'): {
            'address': '0x111111111117dc0aa78b770fa6a738034120c302',
            'decimals': 18,
            'symbol': '1INCH',
        },
        get_token_code('aave', 'erc20'): {
            'address': '0x7fc66500c84a76ad7e9c93437bfc5ac33e2ddae9',
            'decimals': 18,
            'symbol': 'AAVE',
            'gas_limit': '0x41eb0',
        },
        get_token_code('aevo', 'erc20'): {
            'address': '0xb528edbef013aff855ac3c50b381f253af13b997',
            'decimals': 18,
            'symbol': 'AEVO',
        },
        get_token_code('agld', 'erc20'): {
            'address': '0x32353a6c91143bfd6c7d363b546e62a9a2489a20',
            'decimals': 18,
            'symbol': 'AGLD',
        },
        get_token_code('agix', 'erc20'): {
            'address': '0x5b7533812759b45c2b44c19e320ba2cd2681b542',
            'decimals': 8,
            'symbol': 'AGIX',
        },
        get_token_code('alt', 'erc20'): {
            'address': '0x8457ca5040ad67fdebbcc8edce889a335bc0fbfb',
            'decimals': 18,
            'symbol': 'ALT',
        },
        get_token_code('amp', 'erc20'): {
            'address': '0xff20817765cb7f73d4bde2e66e067e58d11095c2',
            'decimals': 18,
            'symbol': 'AMP',
        },
        get_token_code('axl', 'erc20'): {
            'address': '0x467719ad09025fcc6cf6f8311755809d45a5e5f3',
            'decimals': 6,
            'symbol': 'AXL',
        },
        get_token_code('alpha', 'erc20'): {
            'address': '0xa1faa113cbe53436df28ff0aee54275c13b40975',
            'decimals': 18,
            'symbol': 'ALPHA',
        },
        get_token_code('ankr', 'erc20'): {
            'address': '0x8290333cef9e6d528dd5618fb97a76f268f3edd4',
            'decimals': 18,
            'symbol': 'ANKR',
        },
        get_token_code('ant', 'erc20'): {
            'address': '0xa117000000f279d81a1d3cc75430faa017fa5a2e',
            'decimals': 18,
            'symbol': 'ANT',
        },
        get_token_code('ape', 'erc20'): {
            'address': '0x4d224452801aced8b2f0aebe155379bb5d594381',
            'decimals': 18,
            'symbol': 'APE',
        },
        get_token_code('api3', 'erc20'): {
            'address': '0x0b38210ea11411557c13457d4da7dc6ea731b88a',
            'decimals': 18,
            'symbol': 'API3',
        },
        get_token_code('arb', 'erc20'): {
            'address': '0xb50721bcf8d664c30412cfbc6cf7a15145234ad1',
            'decimals': 18,
            'symbol': 'ARB',
        },
        get_token_code('ath', 'erc20'): {
            'address': '0xbe0ed4138121ecfc5c0e56b40517da27e6c5226b',
            'decimals': 18,
            'symbol': 'ATH',
        },
        get_token_code('auction', 'erc20'): {
            'address': '0xa9b1eb5908cfc3cdf91f9b8b3a74108598009096',
            'decimals': 18,
            'symbol': 'AUCTION',
        },
        get_token_code('axs', 'erc20'): {
            'address': '0xbb0e17ef65f82ab018d8edd776e8dd940327b28b',
            'decimals': 18,
            'symbol': 'AXS',
        },
        get_token_code('1b_babydoge', 'erc20'): {
            'address': '0xac57de9c1a09fec648e93eb98875b212db0d460b',
            'decimals': 18,  # native babydoge precision is 9 and system babydoge scale is 1e9 so 9+9=18
            'symbol': '1B_BABYDOGE',
            'scale': '1000000000',
        },
        get_token_code('badger', 'erc20'): {
            'address': '0x3472a5a71965499acd81997a54bba8d852c6e53d',
            'decimals': 18,
            'symbol': 'BADGER',
        },
        get_token_code('bal', 'erc20'): {
            'address': '0xba100000625a3754423978a60c9317c58a424e3d',
            'decimals': 18,
            'symbol': 'BAL',
        },
        get_token_code('banana', 'erc20'): {
            'address': '0x38e68a37e401f7271568cecaac63c6b1e19130b4',
            'decimals': 18,
            'symbol': 'BANANA',
        },
        get_token_code('band', 'erc20'): {
            'address': '0xba11d00c5f74255f56a5e366f4f77f5a186d7f55',
            'decimals': 18,
            'symbol': 'BAND',
            'gas_limit': '0x29810',
        },
        get_token_code('bat', 'erc20'): {
            'address': '0x0d8775f648430679a709e98d2b0cb6250d2887ef',
            'decimals': 18,
            'symbol': 'BAT',
        },
        get_token_code('blur', 'erc20'): {
            'address': '0x5283d291dbcf85356a21ba090e6db59121208b44',
            'decimals': 18,
            'symbol': 'BLUR',
        },
        get_token_code('bico', 'erc20'): {
            'address': '0xf17e65822b568b3903685a7c9f496cf7656cc6c2',
            'decimals': 18,
            'symbol': 'BICO',
            'gas_limit': '0x18700',
        },
        get_token_code('bigtime', 'erc20'): {
            'address': '0x64bc2ca1be492be7185faa2c8835d9b824c8a194',
            'decimals': 18,
            'symbol': 'BIGTIME',
        },
        get_token_code('bnt', 'erc20'): {
            'address': '0x1f573d6fb3f13d689ff844b4ce37794d79a7ff1c',
            'decimals': 18,
            'symbol': 'BNT',
        },
        get_token_code('1m_btt', 'erc20'): {
            'address': '0xc669928185dbce49d2230cc9b0979be6dc797957',
            'decimals': 24,
            'symbol': '1M_BTT',
            'scale': '1000000',
        },
        get_token_code('busd', 'erc20'): {
            'address': '0x4fabb145d64652a948d72533023f6e7a623c7c53',
            'decimals': 18,
            'symbol': 'BUSD',
        },
        get_token_code('celr', 'erc20'): {
            'address': '0x4f9254c83eb525f9fcf346490bbb3ed28a81c667',
            'decimals': 18,
            'symbol': 'CELR',
        },
        get_token_code('chz', 'erc20'): {
            'address': '0x3506424f91fd33084466f402d5d97f05f8e3b4af',
            'decimals': 18,
            'symbol': 'CHZ',
        },
        get_token_code('comp', 'erc20'): {
            'address': '0xc00e94cb662c3520282e6f5717214004a7f26888',
            'decimals': 18,
            'symbol': 'COMP',
        },
        get_token_code('crv', 'erc20'): {
            'address': '0xd533a949740bb3306d119cc777fa900ba034cd52',
            'decimals': 18,
            'symbol': 'CRV',
        },
        get_token_code('cvc', 'erc20'): {
            'address': '0x41e5560054824ea6b0732e656e3ad64e20e94e45',
            'decimals': 8,
            'symbol': 'CVC',
        },
        get_token_code('cvx', 'erc20'): {
            'address': '0x4e3fbd56cd56c3e72c1403e103b45db9da5b9d2b',
            'decimals': 18,
            'symbol': 'CVX',
        },
        get_token_code('dai', 'erc20'): {
            'address': '0x6b175474e89094c44da98b954eedeac495271d0f',
            'decimals': 18,
            'symbol': 'DAI',
        },
        get_token_code('dao', 'erc20'): {
            'address': '0x0f51bb10119727a7e5ea3538074fb341f56b09ad',
            'decimals': 18,
            'symbol': 'DAO',
        },
        get_token_code('dexe', 'erc20'): {
            'address': '0xde4ee8057785a7e8e800db58f9784845a5c2cbd6',
            'decimals': 18,
            'symbol': 'DEXE',
        },
        get_token_code('dydx', 'erc20'): {
            'address': '0x92d6c1e31e14520e676a687f0a93788b716beff5',
            'decimals': 18,
            'symbol': 'DYDX',
            'gas_limit': '0x41eb0',
        },
        get_token_code('egala', 'erc20'): {
            'address': '0xd1d2eb1b1e90b638588728b4130137d262c87cae',
            'decimals': 8,
            'symbol': 'EGALA',
        },
        get_token_code('eigen', 'erc20'): {
            'address': '0xec53bf9167f50cdeb3ae105f56099aaab9061f83',
            'decimals': 18,
            'symbol': 'EIGEN',
        },
        get_token_code('elf', 'erc20'): {
            'address': '0xbf2179859fc6d5bee9bf9158632dc51678a4100e',
            'decimals': 18,
            'symbol': 'ELF',
        },
        get_token_code('enj', 'erc20'): {
            'address': '0xf629cbd94d3791c9250152bd8dfbdf380e2a3b9c',
            'decimals': 18,
            'symbol': 'ENJ',
        },
        get_token_code('ens', 'erc20'): {
            'address': '0xc18360217d8f7ab5e7c516566761ea12ce7f9d72',
            'decimals': 18,
            'symbol': 'ENS',
        },
        get_token_code('ethfi', 'erc20'): {
            'address': '0xfe0c30065b384f05761f15d0cc899d4f9f9cc0eb',
            'decimals': 18,
            'symbol': 'ETHFI',
        },
        get_token_code('fet', 'erc20'): {
            'address': '0xaea46a60368a7bd060eec7df8cba43b7ef41ad85',
            'decimals': 18,
            'symbol': 'FET',
        },
        get_token_code('front', 'erc20'): {
            'address': '0xf8c3527cc04340b208c854e985240c02f7b7793f',
            'decimals': 18,
            'symbol': 'FRONT',
        },
        get_token_code('g', 'erc20'): {
            'address': '0x9c7beba8f6ef6643abd725e45a4e8387ef260649',
            'decimals': 18,
            'symbol': 'G',
        },
        get_token_code('gal', 'erc20'): {
            'address': '0x5faa989af96af85384b8a938c2ede4a7378d9875',
            'decimals': 18,
            'symbol': 'GAL',
        },
        get_token_code('glm', 'erc20'): {
            'address': '0x7dd9c5cba05e151c895fde1cf355c9a1d5da6429',
            'decimals': 18,
            'symbol': 'GLM',
        },
        get_token_code('gno', 'erc20'): {
            'address': '0x6810e776880c02933d47db1b9fc05908e5386b96',
            'decimals': 18,
            'symbol': 'GNO',
        },
        get_token_code('gods', 'erc20'): {
            'address': '0xccc8cb5229b0ac8069c51fd58367fd1e622afd97',
            'decimals': 18,
            'symbol': 'GODS',
        },
        get_token_code('grt', 'erc20'): {
            'address': '0xc944e90c64b2c07662a292be6244bdf05cda44a7',
            'decimals': 18,
            'symbol': 'GRT',
        },
        get_token_code('id', 'erc20'): {
            'address': '0x2dff88a56767223a5529ea5960da7a3f5f766406',
            'decimals': 18,
            'symbol': 'ID',
        },
        get_token_code('ilv', 'erc20'): {
            'address': '0x767fe9edc9e0df98e07454847909b5e959d7ca0e',
            'decimals': 18,
            'symbol': 'ILV',
        },
        get_token_code('imx', 'erc20'): {
            'address': '0xf57e7e7c23978c3caec3c3548e3d615c346e79ff',
            'decimals': 18,
            'symbol': 'IMX',
        },
        get_token_code('inj', 'erc20'): {
            'address': '0xe28b3b32b6c345a34ff64674606124dd5aceca30',
            'decimals': 18,
            'symbol': 'INJ',
        },
        get_token_code('iotx', 'erc20'): {
            'address': '0x6fb3e0a217407efff7ca062d46c26e5d60a14d69',
            'decimals': 18,
            'symbol': 'IOTX',
        },
        get_token_code('knc', 'erc20'): {
            'address': '0xdefa4e8a7bcba345f687a2f1456f5edd9ce97202',
            'decimals': 18,
            'symbol': 'KNC',
        },
        get_token_code('ldo', 'erc20'): {
            'address': '0x5a98fcbea516cf06857215779fd812ca3bef1b32',
            'decimals': 18,
            'symbol': 'LDO',
            'gas_limit': '0x29810',
        },
        get_token_code('link', 'erc20'): {
            'address': '0x514910771af9ca656af840dff83e8264ecf986ca',
            'decimals': 18,
            'symbol': 'LINK',
        },
        get_token_code('looks', 'erc20'): {
            'address': '0xf4d2888d29d722226fafa5d9b24f9164c092421e',
            'decimals': 18,
            'symbol': 'LOOKS',
        },
        get_token_code('lpt', 'erc20'): {
            'address': '0x58b6a8a3302369daec383334672404ee733ab239',
            'decimals': 18,
            'symbol': 'LPT',
        },
        get_token_code('lrc', 'erc20'): {
            'address': '0xbbbbca6a901c926f240b89eacb641d8aec7aeafd',
            'decimals': 18,
            'symbol': 'LRC',
        },
        get_token_code('mana', 'erc20'): {
            'address': '0x0f5d2fb29fb7d3cfee444a200298f468908cc942',
            'decimals': 18,
            'symbol': 'MANA',
        },
        get_token_code('mask', 'erc20'): {
            'address': '0x69af81e73a73b40adf4f3d4223cd9b1ece623074',
            'decimals': 18,
            'symbol': 'MASK',
        },
        get_token_code('metis', 'erc20'): {
            'address': '0x9e32b13ce7f2e80a01932b42553652e053d6ed8e',
            'decimals': 18,
            'symbol': 'METIS',
        },
        get_token_code('morpho', 'erc20'): {
            'address': '0x58d97b57bb95320f9a05dc918aef65434969c2b2',
            'decimals': 18,
            'symbol': 'MORPHO',
        },
        get_token_code('move', 'erc20'): {
            'address': '0x3073f7aaa4db83f95e9fff17424f71d4751a3073',
            'decimals': 8,
            'symbol': 'MOVE',
        },
        get_token_code('neiro', 'erc20'): {
            'address': '0x812ba41e071c7b7fa4ebcfb62df5f45f6fa853ee',
            'decimals': 9,
            'symbol': 'NEIRO',
        },
        get_token_code('nexo', 'erc20'): {
            'address': '0xb62132e35a6c13ee1ee0f84dc5d40bad8d815206',
            'decimals': 18,
            'symbol': 'NEXO',
        },
        get_token_code('pol', 'erc20'): {
            'address': '0x455e53cbb86018ac2b8092fdcd39d8444affc3f6',
            'decimals': 18,
            'symbol': 'POL',
        },
        get_token_code('mdt', 'erc20'): {
            'address': '0x814e0908b12a99fecf5bc101bb5d0b8b5cdf7d26',
            'decimals': 18,
            'symbol': 'MDT',
        },
        get_token_code('meme', 'erc20'): {
            'address': '0xb131f4a55907b10d1f0a50d8ab8fa09ec342cd74',
            'decimals': 18,
            'symbol': 'MEME',
        },
        get_token_code('mkr', 'erc20'): {
            'address': '0x9f8f72aa9304c8b593d555f12ef6589cc3a579a2',
            'decimals': 18,
            'symbol': 'MKR',
        },
        get_token_code('nmr', 'erc20'): {
            'address': '0x1776e1f26f98b1a5df9cd347953a26dd3cb46671',
            'decimals': 18,
            'symbol': 'NMR',
        },
        get_token_code('om', 'erc20'): {
            'address': '0x3593d125a4f7849a1b059e64f4517a86dd60c95d',
            'decimals': 18,
            'symbol': 'OM',
        },
        get_token_code('omg', 'erc20'): {
            'address': '0xd26114cd6ee289accf82350c8d8487fedb8a0c07',
            'decimals': 18,
            'symbol': 'OMG',
        },
        get_token_code('ondo', 'erc20'): {
            'address': '0xfaba6f8e4a5e8ab82f62fe7c39859fa577269be3',
            'decimals': 18,
            'symbol': 'ONDO',
        },
        get_token_code('one', 'erc20'): {
            'address': '0x799a4202c12ca952cb311598a024c80ed371a41e',
            'decimals': 18,
            'symbol': 'ONE',
        },
        get_token_code('orbs', 'erc20'): {
            'address': '0xff56cc6b1e6ded347aa0b7676c85ab0b3d08b0fa',
            'decimals': 18,
            'symbol': 'ORBS',
        },
        get_token_code('paxg', 'erc20'): {
            'address': '0x45804880de22913dafe09f4980848ece6ecbaf78',
            'decimals': 18,
            'symbol': 'PAXG',
        },
        get_token_code('1m_pepe', 'erc20'): {
            'address': '0x6982508145454ce325ddbe47a25d4ec3d2311933',
            'decimals': 24,
            'symbol': '1M_PEPE',
            'scale': '1000000',
        },
        get_token_code('perp', 'erc20'): {
            'address': '0xbc396689893d065f41bc2c6ecbee5e0085233447',
            'decimals': 18,
            'symbol': 'PERP',
        },
        get_token_code('qnt', 'erc20'): {
            'address': '0x4a220e6096b25eadb88358cb44068a3248254675',
            'decimals': 18,
            'symbol': 'QNT',
        },
        get_token_code('ren', 'erc20'): {
            'address': '0x408e41876cccdc0f92210600ef50372656052a38',
            'decimals': 18,
            'symbol': 'REN',
        },
        get_token_code('render', 'erc20'): {
            'address': '0x6de037ef9ad2725eb40118bb1702ebb27e4aeb24',
            'decimals': 18,
            'symbol': 'RENDER',
        },
        get_token_code('rsr', 'erc20'): {
            'address': '0x320623b8e4ff03373931769a31fc52a4e78b5d70',
            'decimals': 18,
            'symbol': 'RSR',
        },
        get_token_code('sand', 'erc20'): {
            'address': '0x3845badade8e6dff049820680d1f14bd3903a5d0',
            'decimals': 18,
            'symbol': 'SAND',
        },
        get_token_code('shib', 'erc20'): {
            'address': '0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce',
            'decimals': 21,
            'symbol': 'SHIB',
            'scale': '1000',
        },
        get_token_code('skl', 'erc20'): {
            'address': '0x00c83aecc790e8a4453e5dd3b0b4b3680501a7a7',
            'decimals': 18,
            'symbol': 'SKL',
            'gas_limit': '0x1adb0',
        },
        get_token_code('slp', 'erc20'): {
            'address': '0xcc8fa225d80b9c7d42f96e9570156c65d6caaa25',
            'decimals': 0,
            'symbol': 'SLP',
        },
        get_token_code('snt', 'erc20'): {
            'address': '0x744d70fdbe2ba4cf95131626614a1763df805b9e',
            'decimals': 18,
            'symbol': 'SNT',
            'gas_limit': '0x29810',
        },
        get_token_code('snx', 'erc20'): {
            'address': '0xc011a73ee8576fb46f5e1c5751ca3b9fe0af2a6f',
            'decimals': 18,
            'symbol': 'SNX',
            'gas_limit': '0x2bf20',
        },
        get_token_code('srm', 'erc20'): {
            'address': '0x476c5e26a75bd202a9683ffd34359c0cc15be0ff',
            'decimals': 6,
            'symbol': 'SRM',
        },
        get_token_code('ssv', 'erc20'): {
            'address': '0x9d65ff81a3c488d585bbfb0bfe3c7707c7917f54',
            'decimals': 18,
            'symbol': 'SSV',
        },
        get_token_code('storj', 'erc20'): {
            'address': '0xb64ef51c888972c908cfacf59b47c1afbc0ab8ac',
            'decimals': 8,
            'symbol': 'STORJ',
        },
        get_token_code('strk', 'erc20'): {
            'address': '0xca14007eff0db1f8135f4c25b34de49ab0d42766',
            'decimals': 18,
            'symbol': 'STRK',
        },
        get_token_code('sushi', 'erc20'): {
            'address': '0x6b3595068778dd592e39a122f4f5a5cf09c90fe2',
            'decimals': 18,
            'symbol': 'SUSHI',
        },
        get_token_code('t', 'erc20'): {
            'address': '0xcdf7028ceab81fa0c6971208e83fa7872994bee5',
            'decimals': 18,
            'symbol': 'T',
        },
        get_token_code('trb', 'erc20'): {
            'address': '0x88df592f8eb5d7bd38bfef7deb0fbc02cf3778a0',
            'decimals': 18,
            'symbol': 'TRB',
        },
        get_token_code('turbo', 'erc20'): {
            'address': '0xa35923162c49cf95e6bf26623385eb431ad920d3',
            'decimals': 18,
            'symbol': 'TURBO',
        },
        get_token_code('uma', 'erc20'): {
            'address': '0x04fa0d235c4abf4bcf4787af4cf447de572ef828',
            'decimals': 18,
            'symbol': 'UMA',
        },
        get_token_code('uni', 'erc20'): {
            'address': '0x1f9840a85d5af5bf1d1762f925bdaddc4201f984',
            'decimals': 18,
            'symbol': 'UNI',
        },
        get_token_code('usdc', 'erc20'): {
            'address': '0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48',
            'decimals': 6,
            'symbol': 'USDC',
        },
        get_token_code('usdt', 'erc20'): {
            'address': '0xdac17f958d2ee523a2206206994597c13d831ec7',
            'decimals': 6,
            'symbol': 'USDT',
        },
        get_token_code('vra', 'erc20'): {
            'address': '0xf411903cbc70a74d22900a5de66a2dda66507255',
            'decimals': 18,
            'symbol': 'VRA',
        },
        get_token_code('w', 'erc20'): {
            'address': '0xb0ffa8000886e57f86dd5264b9582b2ad87b2b91',
            'decimals': 18,
            'symbol': 'W',
        },
        get_token_code('waxp', 'erc20'): {
            'address': '0x2a79324c19ef2b89ea98b23bc669b7e7c9f8a517',
            'decimals': 8,
            'symbol': 'WAXP',
        },
        get_token_code('wbtc', 'erc20'): {
            'address': '0x2260fac5e5542a773aa44fbcfedf7c193bc2c599',
            'decimals': 8,
            'symbol': 'WBTC',
        },
        get_token_code('wld', 'erc20'): {
            'address': '0x163f8c2467924be0ae7b5347228cabf260318753',
            'decimals': 18,
            'symbol': 'WLD',
        },
        get_token_code('woo', 'erc20'): {
            'address': '0x4691937a7508860f876c9c0a2a617e7d9e945d4b',
            'decimals': 18,
            'symbol': 'WOO',
        },
        get_token_code('xaut', 'erc20'): {
            'address': '0x68749665ff8d2d112fa859aa293f07a622782f38',
            'decimals': 6,
            'symbol': 'XAUT',
        },
        get_token_code('yfi', 'erc20'): {
            'address': '0x0bc529c00c6401aef6d220be8c6ea1667f6ad93e',
            'decimals': 18,
            'symbol': 'YFI',
        },
        get_token_code('ygg', 'erc20'): {
            'address': '0x25f8087ead173b73d6e8b84329989a8eea16cf73',
            'decimals': 18,
            'symbol': 'YGG',
        },
        get_token_code('zro', 'erc20'): {
            'address': '0x6985884c4392d348587b19cb9eaaf157f13271cd',
            'decimals': 18,
            'symbol': 'ZRO',
        },
        get_token_code('zrx', 'erc20'): {
            'address': '0xe41d2489571d322189246dafa5ebde1f4699f498',
            'decimals': 18,
            'symbol': 'ZRX',
        },
        get_token_code('ena', 'erc20'): {
            'address': '0x57e114b691db790c35207b2e685d4a43181e6061',
            'decimals': 18,
            'symbol': 'ENA',
        },
        get_token_code('pendle', 'erc20'): {
            'address': '0x808507121b80c02388fad14726482e061b8da827',
            'decimals': 18,
            'symbol': 'PENDLE',
        },
        get_token_code('jasmy', 'erc20'): {
            'address': '0x7420b4b9a0110cdc71fb720908340c03f9bc03ec',
            'decimals': 18,
            'symbol': 'JASMY',
        },
        get_token_code('super', 'erc20'): {
            'address': '0xe53ec727dbdeb9e2d5456c3be40cff031ab40a55',
            'decimals': 18,
            'symbol': 'SUPER',
        },
        get_token_code('cake', 'erc20'): {
            'address': '0x152649ea73beab28c5b49b26eb48f7ead6d4c898',
            'decimals': 18,
            'symbol': 'CAKE',
        },
        get_token_code('ankr', 'erc20'): {
            'address': '0x8290333cef9e6d528dd5618fb97a76f268f3edd4',
            'decimals': 18,
            'symbol': 'ANKR',
        },
        get_token_code('hot', 'erc20'): {
            'address': '0x6c6ee5e31d828de241282b9606c8e98ea48526e2',
            'decimals': 18,
            'symbol': 'HOT',
        },
        get_token_code('safe', 'erc20'): {
            'address': '0x5afe3855358e112b5647b952709e6165e1c1eeee',
            'decimals': 18,
            'symbol': 'SAFE',
        },
        get_token_code('zkj', 'erc20'): {
            'address': '0xc71b5f631354be6853efe9c3ab6b9590f8302e81',
            'decimals': 18,
            'symbol': 'ZKJ',
        },
        get_token_code('pha', 'erc20'): {
            'address': '0x6c5ba91642f10282b576d91922ae6448c9d52f4e',
            'decimals': 18,
            'symbol': 'PHA',
        },
        get_token_code('waxp', 'erc20'): {
            'address': '0x2a79324c19ef2b89ea98b23bc669b7e7c9f8a517',
            'decimals': 8,
            'symbol': 'WAXP',
        },
        get_token_code('fxs', 'erc20'): {
            'address': '0x3432b6a60d23ca0dfca7761b7ab56459d9c964d0',
            'decimals': 18,
            'symbol': 'FXS',
        },
        get_token_code('orbs', 'erc20'): {
            'address': '0xff56cc6b1e6ded347aa0b7676c85ab0b3d08b0fa',
            'decimals': 18,
            'symbol': 'ORBS',
        },
        get_token_code('zent', 'erc20'): {
            'address': '0xdbb7a34bf10169d6d2d0d02a6cbb436cf4381bfa',
            'decimals': 18,
            'symbol': 'ZENT',
        },
        get_token_code('ilv', 'erc20'): {
            'address': '0x767fe9edc9e0df98e07454847909b5e959d7ca0e',
            'decimals': 18,
            'symbol': 'ILV',
        },
        get_token_code('rpl', 'erc20'): {
            'address': '0xd33526068d116ce69f19a9ee46f0bd304f21a51f',
            'decimals': 18,
            'symbol': 'RPL',
        },
        get_token_code('iq', 'erc20'): {
            'address': '0x579cea1889991f68acc35ff5c3dd0621ff29b0c9',
            'decimals': 18,
            'symbol': 'IQ',
        },
        get_token_code('usual', 'erc20'): {
            'address': '0xc4441c2be5d8fa8126822b9929ca0b81ea0de38e',
            'decimals': 18,
            'symbol': 'USUAL',
        },
        get_token_code('bigtime', 'erc20'): {
            'address': '0x64bc2ca1be492be7185faa2c8835d9b824c8a194',
            'decimals': 18,
            'symbol': 'BIGTIME',
        },
        get_token_code('stg', 'erc20'): {
            'address': '0xaf5191b0de278c7286d6c7cc6ab6bb8a73ba2cd6',
            'decimals': 18,
            'symbol': 'STG',
        },
        get_token_code('cow', 'erc20'): {
            'address': '0xdef1ca1fb7fbcdc777520aa7f396b4e015f497ab',
            'decimals': 18,
            'symbol': 'COW',
        },
        get_token_code('people', 'erc20'): {
            'address': '0x7a58c0be72be218b41c608b7fe7c5bb630736c71',
            'decimals': 18,
            'symbol': 'PEOPLE',
        },
        get_token_code('powr', 'erc20'): {
            'address': '0x595832f8fc6bf59c85c527fec3740a1b7a361269',
            'decimals': 6,
            'symbol': 'POWR',
        },
        get_token_code('ach', 'erc20'): {
            'address': '0xed04915c23f00a313a544955524eb7dbd823143d',
            'decimals': 8,
            'symbol': 'ACH',
        }
    },
    'testnet': {
        get_token_code('usdt', 'erc20'): {
            'address': '0x51e7eee7506b92e46a7463d3bf42a4facb52f871',
            'decimals': 6,
            'symbol': 'NBERC20',
        },
        get_token_code('link', 'erc20'): {
            'address': '0x20fe562d797a42dcb3399062ae9546cd06f63280',
            'decimals': 18,
            'symbol': 'LINK',
        },
        get_token_code('dai', 'erc20'): {
            'address': '0xbe19333cb0621d9ff4299057e9ddba163fc92cb4',
            'decimals': 18,
            'symbol': 'DAI',
        },
        get_token_code('ape', 'erc20'): {
            'address': '0xad0ab2261f028f29b4168746b5dce06fb88297e9',
            'decimals': 18,
            'symbol': 'APE',
        },
        get_token_code('mkr', 'erc20'): {
            'address': '0xa8283bdb8a37ac1209740a588ad10bba494c2b61',
            'decimals': 18,
            'symbol': 'MKR',
        },
    },
}

BASE_ERC20_contract_info = {
    'mainnet': {
        get_token_code('aixbt', 'base'): {
            'address': '0x4f9fd6be4a90f2620860d680c0d4d5fb53d1a825',
            'decimals': 18,
            'symbol': 'AIXBT',
        },
        get_token_code('virtual', 'base'): {
            'address': '0x0b3e328455c4059eeb9e3f84b5543f74e24e7e1b',
            'decimals': 18,
            'symbol': 'VIRTUAL',
        },
        get_token_code('kaito', 'base'): {
            'address': '0x98d0baa52b2d063e780de12f615f963fe8537553',
            'decimals': 18,
            'symbol': 'KAITO',
        },
    },
    'testnet': {
    },
}


ERC20_contract_currency = {
    'mainnet': dict((ERC20_contract_info['mainnet'][k]['address'], k) for k in ERC20_contract_info['mainnet'].keys()),
    'testnet': dict((ERC20_contract_info['testnet'][k]['address'], k) for k in ERC20_contract_info['testnet'].keys()),
}

BASE_ERC20_contract_currency = {
    'mainnet': dict(
        (BASE_ERC20_contract_info['mainnet'][k]['address'], k) for k in BASE_ERC20_contract_info['mainnet'].keys()),
    'testnet': dict(
        (BASE_ERC20_contract_info['testnet'][k]['address'], k) for k in BASE_ERC20_contract_info['testnet'].keys()),
}

TRC20_contract_info = {
    'mainnet': {
        get_token_code('1m_btt', 'trc20'): {
            'address': 'TAFjULxiVgT4qWk6UZwjqwZXTSaGaqnVp4',
            'decimals': 24,
            'symbol': '1M_BTT',
            'scale': '1000000',
        },
        get_token_code('1m_nft', 'trc20'): {
            'address': 'TFczxzPhnThNSqr5by8tvxsdCFRRz6cPNq',
            'decimals': 12,  # original decimal places is 6 and scale also is 6 so 6+6=12
            'symbol': '1M_NFT',
            'scale': '1000000',
        },
        get_token_code('jst', 'trc20'): {
            'address': 'TCFLL5dx5ZJdKnWuesXxi1VPwjLVmWZZy9',
            'decimals': 18,
            'symbol': 'JST',
        },
        get_token_code('usdc', 'trc20'): {
            'address': 'TEkxiTehnzSmSe2XqrBj4w32RUN966rdz8',
            'decimals': 6,
            'symbol': 'USDC',
        },
        get_token_code('usdt', 'trc20'): {
            'address': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',
            'decimals': 6,
            'symbol': 'USDT',
        },
    },
    'testnet': {
        get_token_code('usdt', 'trc20'): {
            'address': 'TUCfWd4KMaxddPVCwV4gmiNKUtKSvZNEr7',
            'decimals': 6,
            'symbol': 'NB20',
        },
    },
}
TRC20_contract_currency = {
    'mainnet': dict((TRC20_contract_info['mainnet'][k]['address'], k) for k in TRC20_contract_info['mainnet'].keys()),
    'testnet': dict((TRC20_contract_info['testnet'][k]['address'], k) for k in TRC20_contract_info['testnet'].keys()),
}
BEP20_contract_currency = {
    'mainnet': {
        '0x111111111117dc0aa78b770fa6a738034120c302': get_token_code('inch', 'bep20'),
        '0xfb6115445bff7b52feb98650c87f44907e58f802': get_token_code('aave', 'bep20'),
        '0x3ee2200efb3400fabb9aacf31297cbdd1d435d47': get_token_code('ada', 'bep20'),
        '0xac51066d7bec65dc4589368da368b212745d63e8': get_token_code('alice', 'bep20'),
        '0xa1faa113cbe53436df28ff0aee54275c13b40975': get_token_code('alpha', 'bep20'),
        '0x8457ca5040ad67fdebbcc8edce889a335bc0fbfb': get_token_code('alt', 'bep20'),
        '0xf307910a4c7bbc79691fd374889b36d8531b08e3': get_token_code('ankr', 'bep20'),
        '0x6f769e65c14ebd1f68817f5f1dcdb61cfa2d6f7e': get_token_code('arpa', 'bep20'),
        '0xa2120b9e674d3fc3875f415a7df52e382f141225': get_token_code('ata', 'bep20'),
        '0x0eb3a705fc54725037cc9e008bdede697f62f335': get_token_code('atom', 'bep20'),
        '0xc762043e211571eb34f1ef377e5e8e76914962f9': get_token_code('ape', 'bep20'),
        '0x1ce0c2827e2ef14d5c4f29a091d735a204794041': get_token_code('avax', 'bep20'),
        '0x8b1f4432f943c465a973fedc6d7aa50fc96f1f65': get_token_code('axl', 'bep20'),
        '0x715d400f88c167884bbcc41c5fea407ed4d2f8a0': get_token_code('axs', 'bep20'),
        '0xc748673057861a797275cd8a068abb95a902e8de': get_token_code('1b_babydoge', 'bep20'),
        '0xe02df9e3e622debdd69fb838bb799e3f168902c5': get_token_code('bake', 'bep20'),
        '0xd4ed60d8368a92b5f1ca33af61ef2a94714b2d46': get_token_code('bal', 'bep20'),
        '0xad6caeb32cd2c308980a548bd0bc5aa4306c6c18': get_token_code('band', 'bep20'),
        '0x101d82428437127bf1608f699cd651e6abf9766e': get_token_code('bat', 'bep20'),
        '0x8ff795a6f4d97e7887c79bea79aba5cc76444adf': get_token_code('bch', 'bep20'),
        '0x8443f091997f06a61670b735ed92734f5628692f': get_token_code('bel', 'bep20'),
        '0xa697e272a73744b343528c3bc4702f2565b2f422': get_token_code('1k_bonk', 'bep20'),
        '0x935a544bf5816e3a7c13db2efe3009ffda0acda2': get_token_code('blz', 'bep20'),
        '0x7130d2a12b9bcbfae4f2634d864a1ee1ce3ead9c': get_token_code('btc', 'bep20'),
        '0x352cb5e19b12fc216548a2677bd0fce83bae434b': get_token_code('1m_btt', 'bep20'),
        '0xe9e7cea3dedca5984780bafc599bd69add087d56': get_token_code('busd', 'bep20'),
        '0x6894cde390a3f51155ea41ed24a33a4827d3063d': get_token_code('1k_cat', 'bep20'),
        '0xaec945e04baf28b135fa7c640f624f8d90f1c3a6': get_token_code('c98', 'bep20'),
        '0x1f9f6a696c6fd109cd3956f45dc709d2b3902163': get_token_code('celr', 'bep20'),
        '0x045c4324039da91c52c55df5d785385aab073dcf': get_token_code('cfx', 'bep20'),
        '0x9840652dc04fb9db2c43853633f0f62be6f00f98': get_token_code('cgpt', 'bep20'),
        '0xf9cec8d50f6c8ad3fb6dccec577e05aa32b224fe': get_token_code('chr', 'bep20'),
        '0x52ce071bd9b1c4b00a0b92d298c512478cad67e8': get_token_code('comp', 'bep20'),
        '0xc0041ef357b183448b235a8ea73ce4e4ec8c265f': get_token_code('cookie', 'bep20'),
        '0xadbaf88b39d37dc68775ed1541f1bf83a5a45feb': get_token_code('coti', 'bep20'),
        '0xa8c2b8eec3d368c0253ad3dae65a5f2bbb89c929': get_token_code('ctk', 'bep20'),
        '0x8da443f84fea710266c8eb6bc34b71702d033ef2': get_token_code('ctsi', 'bep20'),
        '0x1af3f329e8be154074d8769d1ffa4ee058b1dbc3': get_token_code('dai', 'bep20'),
        '0x67ee3cb086f8a16f34bee3ca72fad36f7db929e2': get_token_code('dodo', 'bep20'),
        '0xba2ae424d960c26247dd6c32edc70b295c744c43': get_token_code('doge', 'bep20'),
        '0x7083609fce4d1d8dc0c979aab8c869ea2c873402': get_token_code('dot', 'bep20'),
        '0xbf7c81fff98bbe61b40ed186e4afd6ddd01337fe': get_token_code('egld', 'bep20'),
        '0x56b6fb708fc5732dec1afc8d8556423a2edccbd6': get_token_code('eos', 'bep20'),
        '0x3d6545b08693dae087e957cb1180ee38b9e3c25e': get_token_code('etc', 'bep20'),
        '0x2170ed0880ac9a755fd29b2688956bd959f933f8': get_token_code('eth', 'bep20'),
        '0x0d8ce2a99bb6e3b7db580ed848240e4a0f9ae153': get_token_code('fil', 'bep20'),
        '0x5b73a93b4e5e4f1fd27d8b3f8c97d69908b5e284': get_token_code('form', 'bep20'),
        '0xfb5b838b6cfeedc2873ab27866079ac55363d37e': get_token_code('100k_floki', 'bep20'),
        '0xc943c5320b9c18c153d1e2d12cc3074bebfb31a2': get_token_code('flow', 'bep20'),
        '0xad29abb318791d579433d831ed122afeaf29dcfe': get_token_code('ftm', 'bep20'),
        '0x7ddee176f665cd201f93eede625770e2fd911990': get_token_code('pgala', 'bep20'),
        '0x3019bf2a2ef8040c242c9a4c5c4bd4c81678b2a1': get_token_code('gmt', 'bep20'),
        '0xa2b726b1145a4773f68593cf171187d8ebe4d495': get_token_code('inj', 'bep20'),
        '0xd944f1d1e9d5f9bb90b62f9d45e447d989580782': get_token_code('iota', 'bep20'),
        '0x9678e42cebeb63f23197d726b29b1cb20d0064e5': get_token_code('iotx', 'bep20'),
        '0xfe56d5892bdffc7bf58f2e84be1b2c32d21c308b': get_token_code('knc', 'bep20'),
        '0x2aa69e8d25c045b659787bc1f03ce47a388db6e8': get_token_code('ksm', 'bep20'),
        '0x762539b45a1dcce3d36d080f74d1aed37844b878': get_token_code('lina', 'bep20'),
        '0xf8a0bf9cf54bb92f17374d9e9a321e6a111a51bd': get_token_code('link', 'bep20'),
        '0xb59490ab09a0f526cc7305822ac65f2ab12f9723': get_token_code('lit', 'bep20'),
        '0x66e4d38b20173f509a1ff5d82866949e4fe898da': get_token_code('lrc', 'bep20'),
        '0x4338665cbb7b2485a8855a139b75d5e34ab0db94': get_token_code('ltc', 'bep20'),
        '0x2ed9a5c8c13b93955103b9a7c167b67ef4d568a3': get_token_code('mask', 'bep20'),
        '0xcc42724c6683b7e57334c4e856f4c9965ed682bd': get_token_code('pol', 'bep20'),
        '0x5f0da599bb2cccfcf6fdfd7d81743b6020864350': get_token_code('mkr', 'bep20'),
        '0x1fa4a73a3f0133f0025378af00236f3abdee5d63': get_token_code('near', 'bep20'),
        '0xdce07662ca8ebc241316a15b611c89711414dd1a': get_token_code('ocean', 'bep20'),
        '0xfd7b3a77848f1c2d67e05e54d78d174a0c850335': get_token_code('ont', 'bep20'),
        '0xf21768ccbc73ea5b6fd3c687208a7c2def2d966e': get_token_code('reef', 'bep20'),
        '0xd41fdb03ba84762dd66a0af1a6c8540ff1ba5dfb': get_token_code('sfp', 'bep20'),
        '0x2859e4544c4bb03966803b044a93563bd2d0dd4d': get_token_code('shib', 'bep20'),
        '0x9ac983826058b8a9c7aa1c9171441191232e8404': get_token_code('snx', 'bep20'),
        '0x570a5d26f7765ecb712c0924e4de545b89fd43df': get_token_code('sol', 'bep20'),
        '0x947950bcc74888a40ffa2593c5798f11fc9124c4': get_token_code('sushi', 'bep20'),
        '0x47bead2563dcbf3bf2c9407fea4dc236faba485a': get_token_code('sxp', 'bep20'),
        '0x2222227e22102fe3322098e4cbfe18cfebd57c95': get_token_code('tlm', 'bep20'),
        '0x85eac5ac2f758618dfa09bdbe0cf174e7d574d5b': get_token_code('trx', 'bep20'),
        '0x728c5bac3c3e370e372fc4671f9ef6916b814d8b': get_token_code('unfi', 'bep20'),
        '0xbf5140a22578168fd562dccf235e5d43a02ce9b1': get_token_code('uni', 'bep20'),
        '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d': get_token_code('usdc', 'bep20'),
        '0x55d398326f99059ff775485246999027b3197955': get_token_code('usdt', 'bep20'),
        '0x43c934a845205f0b514417d757d7235b8f53f1b9': get_token_code('xlm', 'bep20'),
        '0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe': get_token_code('xrp', 'bep20'),
        '0x16939ef78684453bfdfb47825f8a5f714f12623a': get_token_code('xtz', 'bep20'),
        '0x88f1a5ae2a3bf98aeaf342d26b30a79438c9142e': get_token_code('yfi', 'bep20'),
        '0x7f70642d88cf1c4a3a7abb072b53b929b653eda5': get_token_code('yfii', 'bep20'),
        '0x1ba42e5193dfa8b03d15dd1b86a3113bbbef8eeb': get_token_code('zec', 'bep20'),
        '0xb86abcb37c3a4b64f74f59301aff131a1becc787': get_token_code('zil', 'bep20'),
        '0x5b1f874d0b0c5ee17a495cbb70ab8bf64107a3bd': get_token_code('bnx', 'bep20'),
        '0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82': get_token_code('cake', 'bep20'),
        '0xbdeae1ca48894a1759a8374d63925f21f2ee2639': get_token_code('edu', 'bep20'),
        '0x4b0f1812e5df2a09796481ff14017e6005508003': get_token_code('twt', 'bep20'),
    },
    'testnet': {
        '0x337610d27c682e347c9cd60bd4b3b107c9d34ddd': get_token_code('usdt', 'bep20'),
        '0xd66c6b4f0be8ce5b39d52e0fd1344c389929b378': get_token_code('eth', 'bep20'),
        '0x6ce8da28e2f864420840cf74474eff5fd80e65b8': get_token_code('btc', 'bep20'),
    },
}
BEP20_contract_info = {
    'mainnet': {
        get_token_code('inch', 'bep20'): {
            'address': '0x111111111117dc0aa78b770fa6a738034120c302',
            'decimals': 18,
            'symbol': '1INCH',
        },
        get_token_code('aave', 'bep20'): {
            'address': '0xfb6115445bff7b52feb98650c87f44907e58f802',
            'decimals': 18,
            'symbol': 'AAVE',
        },
        get_token_code('ada', 'bep20'): {
            'address': '0x3ee2200efb3400fabb9aacf31297cbdd1d435d47',
            'decimals': 18,
            'symbol': 'ADA',
        },
        get_token_code('alice', 'bep20'): {
            'address': '0xac51066d7bec65dc4589368da368b212745d63e8',
            'decimals': 6,
            'symbol': 'ALICE',
        },
        get_token_code('alpha', 'bep20'): {
            'address': '0xa1faa113cbe53436df28ff0aee54275c13b40975',
            'decimals': 18,
            'symbol': 'ALPHA',
        },
        get_token_code('alt', 'bep20'): {
            'address': '0x8457ca5040ad67fdebbcc8edce889a335bc0fbfb',
            'decimals': 18,
            'symbol': 'ALT',
        },
        get_token_code('ankr', 'bep20'): {
            'address': '0xf307910a4c7bbc79691fd374889b36d8531b08e3',
            'decimals': 18,
            'symbol': 'ANKR',
        },
        get_token_code('arpa', 'bep20'): {
            'address': '0x6f769e65c14ebd1f68817f5f1dcdb61cfa2d6f7e',
            'decimals': 18,
            'symbol': 'ARPA',
        },
        get_token_code('ata', 'bep20'): {
            'address': '0xa2120b9e674d3fc3875f415a7df52e382f141225',
            'decimals': 18,
            'symbol': 'ATA',
        },
        get_token_code('atom', 'bep20'): {
            'address': '0x0eb3a705fc54725037cc9e008bdede697f62f335',
            'decimals': 18,
            'symbol': 'ATOM',
        },
        get_token_code('avax', 'bep20'): {
            'address': '0x1ce0c2827e2ef14d5c4f29a091d735a204794041',
            'decimals': 18,
            'symbol': 'AVAX',
        },
        get_token_code('ape', 'bep20'): {
            'address': '0xc762043e211571eb34f1ef377e5e8e76914962f9',
            'decimals': 18,
            'symbol': 'APE',
        },
        get_token_code('axl', 'bep20'): {
            'address': '0x8b1f4432f943c465a973fedc6d7aa50fc96f1f65',
            'decimals': 6,
            'symbol': 'AXL',
        },
        get_token_code('axs', 'bep20'): {
            'address': '0x715d400f88c167884bbcc41c5fea407ed4d2f8a0',
            'decimals': 18,
            'symbol': 'AXS',
        },
        get_token_code('1b_babydoge', 'bep20'): {
            'address': '0xc748673057861a797275cd8a068abb95a902e8de',
            'decimals': 18,  # native babydoge precision is 9 and system babydoge scale is 1e9 so 9+9=18
            'symbol': '1B_BABYDOGE',
            'scale': '1000000000',
        },
        get_token_code('bake', 'bep20'): {
            'address': '0xe02df9e3e622debdd69fb838bb799e3f168902c5',
            'decimals': 18,
            'symbol': 'BAKE',
        },
        get_token_code('bal', 'bep20'): {
            'address': '0xd4ed60d8368a92b5f1ca33af61ef2a94714b2d46',
            'decimals': 18,
            'symbol': 'BAL',
        },
        get_token_code('band', 'bep20'): {
            'address': '0xad6caeb32cd2c308980a548bd0bc5aa4306c6c18',
            'decimals': 18,
            'symbol': 'BAND',
        },
        get_token_code('bat', 'bep20'): {
            'address': '0x101d82428437127bf1608f699cd651e6abf9766e',
            'decimals': 18,
            'symbol': 'BAT',
        },
        get_token_code('bch', 'bep20'): {
            'address': '0x8ff795a6f4d97e7887c79bea79aba5cc76444adf',
            'decimals': 18,
            'symbol': 'BCH',
        },
        get_token_code('bel', 'bep20'): {
            'address': '0x8443f091997f06a61670b735ed92734f5628692f',
            'decimals': 18,
            'symbol': 'BEL',
        },
        get_token_code('blz', 'bep20'): {
            'address': '0x935a544bf5816e3a7c13db2efe3009ffda0acda2',
            'decimals': 18,
            'symbol': 'BLZ',
        },
        get_token_code('1k_bonk', 'bep20'): {
            'address': '0xa697e272a73744b343528c3bc4702f2565b2f422',
            'decimals': 8,  # base precision 5 and scale precision 3
            'symbol': '1K_BONK',
            'scale': 1000,
        },
        get_token_code('btc', 'bep20'): {
            'address': '0x7130d2a12b9bcbfae4f2634d864a1ee1ce3ead9c',
            'decimals': 18,
            'symbol': 'BTC',
        },
        get_token_code('1m_btt', 'bep20'): {
            'address': '0x352cb5e19b12fc216548a2677bd0fce83bae434b',
            'decimals': 24,
            'symbol': '1M_BTT',
            'scale': '1000000',
        },
        get_token_code('busd', 'bep20'): {
            'address': '0xe9e7cea3dedca5984780bafc599bd69add087d56',
            'decimals': 18,
            'symbol': 'BUSD',
        },
        get_token_code('c98', 'bep20'): {
            'address': '0xaec945e04baf28b135fa7c640f624f8d90f1c3a6',
            'decimals': 18,
            'symbol': 'C98',
        },
        get_token_code('1k_cat', 'bep20'): {
            'address': '0x6894cde390a3f51155ea41ed24a33a4827d3063d',
            'decimals': 21,  # base precision 18 and scale precision 3
            'symbol': '1K_CAT',
            'scale': '1000',
        },
        get_token_code('celr', 'bep20'): {
            'address': '0x1f9f6a696c6fd109cd3956f45dc709d2b3902163',
            'decimals': 18,
            'symbol': 'CELR',
        },
        get_token_code('cfx', 'bep20'): {
            'address': '0x045c4324039da91c52c55df5d785385aab073dcf',
            'decimals': 18,
            'symbol': 'CFX',
        },
        get_token_code('cgpt', 'bep20'): {
            'address': '0x9840652dc04fb9db2c43853633f0f62be6f00f98',
            'decimals': 18,
            'symbol': 'CGPT',
        },
        get_token_code('chr', 'bep20'): {
            'address': '0xf9cec8d50f6c8ad3fb6dccec577e05aa32b224fe',
            'decimals': 6,
            'symbol': 'CHR',
        },
        get_token_code('cookie', 'bep20'): {
            'address': '0xc0041ef357b183448b235a8ea73ce4e4ec8c265f',
            'decimals': 18,
            'symbol': 'COOKIE',
        },
        get_token_code('comp', 'bep20'): {
            'address': '0x52ce071bd9b1c4b00a0b92d298c512478cad67e8',
            'decimals': 18,
            'symbol': 'COMP',
        },
        get_token_code('coti', 'bep20'): {
            'address': '0xadbaf88b39d37dc68775ed1541f1bf83a5a45feb',
            'decimals': 18,
            'symbol': 'COTI',
        },
        get_token_code('ctk', 'bep20'): {
            'address': '0xa8c2b8eec3d368c0253ad3dae65a5f2bbb89c929',
            'decimals': 6,
            'symbol': 'CTK',
        },
        get_token_code('ctsi', 'bep20'): {
            'address': '0x8da443f84fea710266c8eb6bc34b71702d033ef2',
            'decimals': 18,
            'symbol': 'CTSI',
        },
        get_token_code('dai', 'bep20'): {
            'address': '0x1af3f329e8be154074d8769d1ffa4ee058b1dbc3',
            'decimals': 18,
            'symbol': 'DAI',
        },
        get_token_code('dodo', 'bep20'): {
            'address': '0x67ee3cb086f8a16f34bee3ca72fad36f7db929e2',
            'decimals': 18,
            'symbol': 'DODO',
        },
        get_token_code('doge', 'bep20'): {
            'address': '0xba2ae424d960c26247dd6c32edc70b295c744c43',
            'decimals': 8,
            'symbol': 'DOGE',
        },
        get_token_code('dot', 'bep20'): {
            'address': '0x7083609fce4d1d8dc0c979aab8c869ea2c873402',
            'decimals': 18,
            'symbol': 'DOT',
        },
        get_token_code('egld', 'bep20'): {
            'address': '0xbf7c81fff98bbe61b40ed186e4afd6ddd01337fe',
            'decimals': 18,
            'symbol': 'EGLD',
        },
        get_token_code('eos', 'bep20'): {
            'address': '0x56b6fb708fc5732dec1afc8d8556423a2edccbd6',
            'decimals': 18,
            'symbol': 'EOS',
        },
        get_token_code('etc', 'bep20'): {
            'address': '0x3d6545b08693dae087e957cb1180ee38b9e3c25e',
            'decimals': 18,
            'symbol': 'ETC',
        },
        get_token_code('eth', 'bep20'): {
            'address': '0x2170ed0880ac9a755fd29b2688956bd959f933f8',
            'decimals': 18,
            'symbol': 'ETH',
        },
        get_token_code('fil', 'bep20'): {
            'address': '0x0d8ce2a99bb6e3b7db580ed848240e4a0f9ae153',
            'decimals': 18,
            'symbol': 'FIL',
        },
        get_token_code('form', 'bep20'): {
            'address': '0x5b73a93b4e5e4f1fd27d8b3f8c97d69908b5e284',
            'decimals': 18,
            'symbol': 'FORM',
        },
        get_token_code('100k_floki', 'bep20'): {
            'address': '0xfb5b838b6cfeedc2873ab27866079ac55363d37e',
            'decimals': 14,  # native floki decimals is 9 and system scale is 5 so 9+5=14
            'symbol': '100K_FLOKI',
            'scale': '100000',
        },
        get_token_code('flow', 'bep20'): {
            'address': '0xc943c5320b9c18c153d1e2d12cc3074bebfb31a2',
            'decimals': 18,
            'symbol': 'FLOW',
        },
        get_token_code('ftm', 'bep20'): {
            'address': '0xad29abb318791d579433d831ed122afeaf29dcfe',
            'decimals': 18,
            'symbol': 'FTM',
        },
        get_token_code('pgala', 'bep20'): {
            'address': '0x7ddee176f665cd201f93eede625770e2fd911990',
            'decimals': 18,
            'symbol': 'PGALA',
            'from_block': 22762800,
        },
        get_token_code('gala', 'bep20'): {
            'address': '0x7ddee176f665cd201f93eede625770e2fd911990',
            'decimals': 18,
            'symbol': 'PGALA',
        },
        get_token_code('inj', 'bep20'): {
            'address': '0xa2b726b1145a4773f68593cf171187d8ebe4d495',
            'decimals': 18,
            'symbol': 'INJ',
        },
        get_token_code('iota', 'bep20'): {
            'address': '0xd944f1d1e9d5f9bb90b62f9d45e447d989580782',
            'decimals': 6,
            'symbol': 'IOTA',
        },
        get_token_code('iotx', 'bep20'): {
            'address': '0x9678e42cebeb63f23197d726b29b1cb20d0064e5',
            'decimals': 18,
            'symbol': 'IOTX',
        },
        get_token_code('gmt', 'bep20'): {
            'address': '0x3019bf2a2ef8040c242c9a4c5c4bd4c81678b2a1',
            'decimals': 8,
            'symbol': 'GMT',
        },
        get_token_code('knc', 'bep20'): {
            'address': '0xfe56d5892bdffc7bf58f2e84be1b2c32d21c308b',
            'decimals': 18,
            'symbol': 'KNC',
        },
        get_token_code('ksm', 'bep20'): {
            'address': '0x2aa69e8d25c045b659787bc1f03ce47a388db6e8',
            'decimals': 18,
            'symbol': 'KSM',
        },
        get_token_code('lina', 'bep20'): {
            'address': '0x762539b45a1dcce3d36d080f74d1aed37844b878',
            'decimals': 18,
            'symbol': 'LINA',
        },
        get_token_code('link', 'bep20'): {
            'address': '0xf8a0bf9cf54bb92f17374d9e9a321e6a111a51bd',
            'decimals': 18,
            'symbol': 'LINK',
        },
        get_token_code('lit', 'bep20'): {
            'address': '0xb59490ab09a0f526cc7305822ac65f2ab12f9723',
            'decimals': 18,
            'symbol': 'LIT',
        },
        get_token_code('lrc', 'bep20'): {
            'address': '0x66e4d38b20173f509a1ff5d82866949e4fe898da',
            'decimals': 18,
            'symbol': 'LRC',
        },
        get_token_code('ltc', 'bep20'): {
            'address': '0x4338665cbb7b2485a8855a139b75d5e34ab0db94',
            'decimals': 18,
            'symbol': 'LTC',
        },
        get_token_code('mask', 'bep20'): {
            'address': '0x2ed9a5c8c13b93955103b9a7c167b67ef4d568a3',
            'decimals': 18,
            'symbol': 'MASK',
        },
        get_token_code('pol', 'bep20'): {
            'address': '0xcc42724c6683b7e57334c4e856f4c9965ed682bd',
            'decimals': 18,
            'symbol': 'POL',
        },
        get_token_code('mkr', 'bep20'): {
            'address': '0x5f0da599bb2cccfcf6fdfd7d81743b6020864350',
            'decimals': 18,
            'symbol': 'MKR',
        },
        get_token_code('near', 'bep20'): {
            'address': '0x1fa4a73a3f0133f0025378af00236f3abdee5d63',
            'decimals': 18,
            'symbol': 'NEAR',
        },
        get_token_code('ocean', 'bep20'): {
            'address': '0xdce07662ca8ebc241316a15b611c89711414dd1a',
            'decimals': 18,
            'symbol': 'OCEAN',
        },
        get_token_code('ont', 'bep20'): {
            'address': '0xfd7b3a77848f1c2d67e05e54d78d174a0c850335',
            'decimals': 18,
            'symbol': 'ONT',
        },
        get_token_code('reef', 'bep20'): {
            'address': '0xf21768ccbc73ea5b6fd3c687208a7c2def2d966e',
            'decimals': 18,
            'symbol': 'REEF',
        },
        get_token_code('sfp', 'bep20'): {
            'address': '0xd41fdb03ba84762dd66a0af1a6c8540ff1ba5dfb',
            'decimals': 18,
            'symbol': 'SFP',
        },
        get_token_code('shib', 'bep20'): {
            'address': '0x2859e4544c4bb03966803b044a93563bd2d0dd4d',
            'decimals': 21,
            'symbol': 'SHIB',
            'scale': '1000',
        },
        get_token_code('snx', 'bep20'): {
            'address': '0x9ac983826058b8a9c7aa1c9171441191232e8404',
            'decimals': 18,
            'symbol': 'SNX',
        },
        get_token_code('sol', 'bep20'): {
            'address': '0x570a5d26f7765ecb712c0924e4de545b89fd43df',
            'decimals': 18,
            'symbol': 'SOL',
        },
        get_token_code('sushi', 'bep20'): {
            'address': '0x947950bcc74888a40ffa2593c5798f11fc9124c4',
            'decimals': 18,
            'symbol': 'SUSHI',
        },
        get_token_code('sxp', 'bep20'): {
            'address': '0x47bead2563dcbf3bf2c9407fea4dc236faba485a',
            'decimals': 18,
            'symbol': 'SXP',
        },
        get_token_code('tlm', 'bep20'): {
            'address': '0x2222227e22102fe3322098e4cbfe18cfebd57c95',
            'decimals': 4,
            'symbol': 'TLM',
        },
        get_token_code('trx', 'bep20'): {
            'address': '0x85eac5ac2f758618dfa09bdbe0cf174e7d574d5b',
            'decimals': 18,
            'symbol': 'TRX',
        },
        get_token_code('unfi', 'bep20'): {
            'address': '0x728c5bac3c3e370e372fc4671f9ef6916b814d8b',
            'decimals': 18,
            'symbol': 'UNFI',
        },
        get_token_code('uni', 'bep20'): {
            'address': '0xbf5140a22578168fd562dccf235e5d43a02ce9b1',
            'decimals': 18,
            'symbol': 'UNI',
        },
        get_token_code('usdc', 'bep20'): {
            'address': '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d',
            'decimals': 18,
            'symbol': 'USDC',
        },
        get_token_code('usdt', 'bep20'): {
            'address': '0x55d398326f99059ff775485246999027b3197955',
            'decimals': 18,
            'symbol': 'USDT',
        },
        get_token_code('xlm', 'bep20'): {
            'address': '0x43c934a845205f0b514417d757d7235b8f53f1b9',
            'decimals': 18,
            'symbol': 'XLM',
        },
        get_token_code('xrp', 'bep20'): {
            'address': '0x1d2f0da169ceb9fc7b3144628db156f3f6c60dbe',
            'decimals': 18,
            'symbol': 'XRP',
        },
        get_token_code('xtz', 'bep20'): {
            'address': '0x16939ef78684453bfdfb47825f8a5f714f12623a',
            'decimals': 18,
            'symbol': 'XTZ',
        },
        get_token_code('yfi', 'bep20'): {
            'address': '0x88f1a5ae2a3bf98aeaf342d26b30a79438c9142e',
            'decimals': 18,
            'symbol': 'YFI',
        },
        get_token_code('yfii', 'bep20'): {
            'address': '0x7f70642d88cf1c4a3a7abb072b53b929b653eda5',
            'decimals': 18,
            'symbol': 'YFII',
        },
        get_token_code('zec', 'bep20'): {
            'address': '0x1ba42e5193dfa8b03d15dd1b86a3113bbbef8eeb',
            'decimals': 18,
            'symbol': 'ZEC',
        },
        get_token_code('zil', 'bep20'): {
            'address': '0xb86abcb37c3a4b64f74f59301aff131a1becc787',
            'decimals': 12,
            'symbol': 'ZIL',
        },
        get_token_code('bnx', 'bep20'): {
            'address': '0x5b1f874d0b0c5ee17a495cbb70ab8bf64107a3bd',
            'decimals': 18,
            'symbol': 'BNX',
        },
        get_token_code('cake', 'bep20'): {
            'address': '0x0e09fabb73bd3ade0a17ecc321fd13a19e81ce82',
            'decimals': 18,
            'symbol': 'CAKE',
        },
        get_token_code('edu', 'bep20'): {
            'address': '0xbdeae1ca48894a1759a8374d63925f21f2ee2639',
            'decimals': 18,
            'symbol': 'EDU',
        },
        get_token_code('twt', 'bep20'): {
            'address': '0x4b0f1812e5df2a09796481ff14017e6005508003',
            'decimals': 18,
            'symbol': 'TWT',
        },
    },
    'testnet': {
        get_token_code('usdt', 'bep20'): {
            'address': '0x337610d27c682e347c9cd60bd4b3b107c9d34ddd',
            'decimals': 18,
            'symbol': 'USDT',
        },
        get_token_code('eth', 'bep20'): {
            'address': '0xd66c6b4f0be8ce5b39d52e0fd1344c389929b378',
            'decimals': 18,
            'symbol': 'ETH',
        },
        get_token_code('btc', 'bep20'): {
            'address': '0x6ce8da28e2f864420840cf74474eff5fd80e65b8',
            'decimals': 18,
            'symbol': 'BTCB'
        },
    },
}
opera_ftm_contract_currency = {
    'mainnet': {
        '0x6a07a792ab2965c72a5b8088d3a069a7ac3a993b': get_token_code('aave', 'ftm'),
        # '0x04068da6c83afcfa0e13ba15a6696662335d5b75': get_token_code('usdc', 'ftm'),
        '0x049d68029688eabf473097a2fc38ef61633a3c7a': get_token_code('usdt', 'ftm'),
        '0x8d11ec38a3eb5e956b052f67da8bdc9bef8abf3e': get_token_code('dai', 'ftm'),
        '0xb3654dc3d10ea7645f8319668e8f54d2574fbdc8': get_token_code('link', 'ftm'),
        '0x321162cd933e2be498cd2267a90534a804051b11': get_token_code('btc', 'ftm'),
        '0x74b23882a30290451a17c44f4f05243b6b58c76d': get_token_code('eth', 'ftm'),
    },
    'testnet': {
    },
}
opera_ftm_contract_info = {
    'mainnet': {
        get_token_code('aave', 'ftm'): {
            'address': '0x6a07a792ab2965c72a5b8088d3a069a7ac3a993b',
            'decimals': 18,
            'symbol': 'AAVE'
        },
        # get_token_code('usdc', 'ftm'): {
        #     'address': '0x04068da6c83afcfa0e13ba15a6696662335d5b75',
        #     'decimals': 6,
        #     'symbol': 'USDC'
        # },
        get_token_code('usdt', 'ftm'): {
            'address': '0x049d68029688eabf473097a2fc38ef61633a3c7a',
            'decimals': 6,
            'symbol': 'fUSDT'
        },
        get_token_code('dai', 'ftm'): {
            'address': '0x8d11ec38a3eb5e956b052f67da8bdc9bef8abf3e',
            'decimals': 18,
            'symbol': 'DAI'
        },
        get_token_code('link', 'ftm'): {
            'address': '0xb3654dc3d10ea7645f8319668e8f54d2574fbdc8',
            'decimals': 18,
            'symbol': 'LINK'
        },
        get_token_code('btc', 'ftm'): {
            'address': '0x321162cd933e2be498cd2267a90534a804051b11',
            'decimals': 8,
            'symbol': 'WBTC'
        },
        get_token_code('eth', 'ftm'): {
            'address': '0x74b23882a30290451a17c44f4f05243b6b58c76d',
            'decimals': 18,
            'symbol': 'WETH'
        },
    },
    'testnet': {
        get_token_code('link', 'ftm'): {
            'address': '0xe0de5938c35c03936cd7f684b6f57c1652618846',
            'decimals': 6,
            'symbol': 'LINK'
        }
    },
}
ton_contract_currency = {
    'mainnet': {
        'EQAvlWFDxGF2lXm67y4yzC17wYKD9A0guwPkMs1gOsM__NOT': get_token_code('not', 'jetton'),
        'EQCvxJy4eG8hyHBFsZ7eePxrRsUQSFE_jpptRAYBmcG_DOGS': get_token_code('dogs', 'jetton'),
        'EQD-cvR0Nz6XAyRBvbhz-abTrRC6sI5tvHvvpeQraV9UAAD7': get_token_code('cati', 'jetton'),
        'EQAJ8uWd7EBqsmpSWaRdf_I-8R8-XHwh3gsNKhy-UrdrPcUo': get_token_code('hmstr', 'jetton'),
        'EQB4zZusHsbU2vVTPqjhlokIOoiZhEdCMT703CWEzhTOo__X': get_token_code('x', 'jetton'),
        'EQCuPm01HldiduQ55xaBF_1kaW_WAUy5DHey8suqzU_MAJOR': get_token_code('major', 'jetton'),
    },
    'testnet': {
    },
}
ton_contract_info = {
    'mainnet': {
        get_token_code('cati', 'jetton'): {
            'address': 'EQD-cvR0Nz6XAyRBvbhz-abTrRC6sI5tvHvvpeQraV9UAAD7',
            'decimals': 9,
            'symbol': 'CATI'
        },
        get_token_code('dogs', 'jetton'): {
            'address': 'EQCvxJy4eG8hyHBFsZ7eePxrRsUQSFE_jpptRAYBmcG_DOGS',
            'decimals': 9,
            'symbol': 'DOGS'
        },
        get_token_code('hmstr', 'jetton'): {
            'address': 'EQAJ8uWd7EBqsmpSWaRdf_I-8R8-XHwh3gsNKhy-UrdrPcUo',
            'decimals': 9,
            'symbol': 'HMSTR'
        },
        get_token_code('not', 'jetton'): {
            'address': 'EQAvlWFDxGF2lXm67y4yzC17wYKD9A0guwPkMs1gOsM__NOT',
            'decimals': 9,
            'symbol': 'NOT'
        },
        get_token_code('usdt', 'jetton'): {
            'address': 'EQCxE6mUtQJKFnGfaROTKOt1lZbDiiX1kCixRv7Nw2Id_sDs',
            'decimals': 9,
            'symbol': 'USDT'
        },
        get_token_code('x', 'jetton'): {
            'address': 'EQB4zZusHsbU2vVTPqjhlokIOoiZhEdCMT703CWEzhTOo__X',
            'decimals': 9,
            'symbol': 'X'
        },
        get_token_code('major', 'jetton'): {
            'address': 'EQCuPm01HldiduQ55xaBF_1kaW_WAUy5DHey8suqzU_MAJOR',
            'decimals': 9,
            'symbol': 'MAJOR'
        },
    },
    'testnet': {
    },
}

sol_contract_info = {
    'mainnet': {
        get_token_code('1k_bonk', 'spl_token'): {
            'address': 'DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263',
            'decimals': 8,
            'symbol': '1K_BONK',
            'scale': 1000
        },
        get_token_code('usdt', 'spl_token'): {
            'address': 'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',
            'decimals': 6,
            'symbol': 'USDT',
        },
        get_token_code('wif', 'spl_token'): {
            'address': 'EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm',
            'decimals': 6,
            'symbol': 'WIF',
        },
        get_token_code('ray', 'spl_token'): {
            'address': '4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R',
            'decimals': 6,
            'symbol': 'RAY',
        },
        get_token_code('tnsr', 'spl_token'): {
            'address': 'TNSRxcUxoT9xBG3de7PiJyTDYu7kskLqcpddxnEJAS6',
            'decimals': 9,
            'symbol': 'TNSR',
        },
        get_token_code('render', 'spl_token'): {
            'address': 'rndrizKT3MK1iimdxRdWabcF7Zg7AR5T4nud4EkHBof',
            'decimals': 8,
            'symbol': 'RENDER',
        },
        get_token_code('vine', 'spl_token'): {
            'address': '6AJcP7wuLwmRYLBNbi825wgguaPsWzPBEHcHndpRpump',
            'decimals': 6,
            'symbol': 'VINE',
        },
        get_token_code('act', 'spl_token'): {
            'address': 'GJAFwWjJ3vnTsrQVabjBVK2TYB1YtRCQXRDfDgUnpump',
            'decimals': 6,
            'symbol': 'ACT',
        },
        get_token_code('goat', 'spl_token'): {
            'address': 'CzLSujWBLFsSjncfkh59rUFqvafWcY5tzedWJSuypump',
            'decimals': 6,
            'symbol': 'GOAT',
        },
        get_token_code('pengu', 'spl_token'): {
            'address': '2zMMhcVQEXDtdE6vsFS7S7D5oUodfJHE8vd1gnBouauv',
            'decimals': 6,
            'symbol': 'PENGU',
        },
        get_token_code('jup', 'spl_token'): {
            'address': 'JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN',
            'decimals': 6,
            'symbol': 'JUP',
        },
        get_token_code('io', 'spl_token'): {
            'address': 'BZLbGTNCSFfoth2GYDtwr7e4imWzpR5jqcUuGEwr646K',
            'decimals': 8,
            'symbol': 'IO',
        }

    },
    'testnet': {},
}

SPLTOKEN_contract_currency = {
    'mainnet': {sol_contract_info['mainnet'][k]['address']: k for k in sol_contract_info['mainnet']},
    'testnet': {sol_contract_info['testnet'][k]['address']: k for k in sol_contract_info['testnet']}
}

polygon_ERC20_contract_info = {
    'mainnet': {
        get_token_code('aave', 'polygon'): {
            'address': '0xd6df932a45c0f255f85145f286ea0b292b21c90b',
            'decimals': 18,
            'symbol': 'AAVE'
        },
        get_token_code('btc', 'polygon'): {
            'address': '0x1bfd67037b42cf73acf2047067bd4f2c47d9bfd6',
            'decimals': 8,
            'symbol': 'WBTC'
        },
        get_token_code('dai', 'polygon'): {
            'address': '0x8f3cf7ad23cd3cadbd9735aff958023239c6a063',
            'decimals': 18,
            'symbol': 'DAI'
        },
        get_token_code('eth', 'polygon'): {
            'address': '0x7ceb23fd6bc0add59e62ac25578270cff1b9f619',
            'decimals': 18,
            'symbol': 'WETH'
        },
        get_token_code('link', 'polygon'): {
            'address': '0x53e0bca35ec356bd5dddfebbd1fc0fd03fabad39',
            'decimals': 18,
            'symbol': 'Link'
        },
        get_token_code('usdc', 'polygon'): {
            'address': '0x2791bca1f2de4661ed88a30c99a7a9449aa84174',
            'decimals': 6,
            'symbol': 'USDC'
        },
        get_token_code('usdt', 'polygon'): {
            'address': '0xc2132d05d31c914a87c6611c10748aeb04b58e8f',
            'decimals': 6,
            'symbol': 'USDT'
        },
    },
    'testnet': {
        get_token_code('link', 'polygon'): {
            'address': '0x326c977e6efc84e512bb9c30f76e30c160ed06fb',
            'decimals': 18,
            'symbol': 'LINK'
        }
    },
}
polygon_ERC20_contract_currency = {
    'mainnet': dict((polygon_ERC20_contract_info['mainnet'][k]['address'], k) for k in
                    polygon_ERC20_contract_info['mainnet'].keys()),
    'testnet': dict((polygon_ERC20_contract_info['testnet'][k]['address'], k) for k in
                    polygon_ERC20_contract_info['testnet'].keys()),
}
arbitrum_ERC20_contract_info = {
    'mainnet': {
        get_token_code('arb', 'arbitrum'): {
            'address': '0x912ce59144191c1204e64559fe8253a0e49e6548',
            'decimals': 18,
            'symbol': 'ARB'
        },
        get_token_code('axl', 'arbitrum'): {
            'address': '0x23ee2343b892b1bb63503a4fabc840e0e2c6810f',
            'decimals': 6,
            'symbol': 'AXL'
        },
        get_token_code('dai', 'arbitrum'): {
            'address': '0xda10009cbd5d07dd0cecc66161fc93d7c9000da1',
            'decimals': 18,
            'symbol': 'DAI'
        },
        get_token_code('gmx', 'arbitrum'): {
            'address': '0xfc5a1a6eb076a2c7ad06ed22c90d7e710e35ad0a',
            'decimals': 18,
            'symbol': 'GMX'
        },
        get_token_code('magic', 'arbitrum'): {
            'address': '0x539bde0d7dbd336b79148aa742883198bbf60342',
            'decimals': 18,
            'symbol': 'MAGIC'
        },
        get_token_code('rdnt', 'arbitrum'): {
            'address': '0x3082cc23568ea640225c2467653db90e9250aaa0',
            'decimals': 18,
            'symbol': 'RDNT'
        },
        get_token_code('usdc', 'arbitrum'): {
            'address': '0xff970a61a04b1ca14834a43f5de4533ebddb5cc8',
            'decimals': 6,
            'symbol': 'USDC'
        },
        get_token_code('usdt', 'arbitrum'): {
            'address': '0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9',
            'decimals': 6,
            'symbol': 'USDT'
        },
        get_token_code('zro', 'arbitrum'): {
            'address': '0x6985884c4392d348587b19cb9eaaf157f13271cd',
            'decimals': 18,
            'symbol': 'ZRO',
        },
        get_token_code('anime', 'arbitrum'): {
            'address': '0x37a645648df29205c6261289983fb04ecd70b4b3',
            'decimals': 18,
            'symbol': 'ANIME',
        },
        get_token_code('xai', 'arbitrum'): {
            'address': '0x4cb9a7ae498cedcbb5eae9f25736ae7d428c9d66',
            'decimals': 18,
            'symbol': 'XAI',
        }
    },
    'testnet': {
    }
}

arbitrum_ERC20_contract_currency = {
    'mainnet': dict((arbitrum_ERC20_contract_info['mainnet'][k]['address'], k) for k in
                    arbitrum_ERC20_contract_info['mainnet'].keys()),
    'testnet': dict((arbitrum_ERC20_contract_info['testnet'][k]['address'], k) for k in
                    arbitrum_ERC20_contract_info['testnet'].keys()),
}

avalanche_ERC20_contract_info = {
    'mainnet': {
    },
    'testnet': {
    },
}
avalanche_ERC20_contract_currency = {
    'mainnet': {
    },
    'testnet': {
    },
}
harmony_ERC20_contract_info = {
    'mainnet': {
    },
    'testnet': {
    },
}
harmony_ERC20_contract_currency = {
    'mainnet': {
    },
    'testnet': {
    },
}
sonic_ERC20_contract_info = {
    'mainnet': {
    },
    'testnet': {
    },
}
sonic_ERC20_contract_currency = {
    'mainnet': {
    },
    'testnet': {
    },
}
ETC_ERC20_contract_info = {
    'mainnet': {
    },
    'testnet': {
    },
}
CONTRACT_INFO = {
    CurrenciesNetworkName.ETH: ERC20_contract_info,
    CurrenciesNetworkName.BSC: BEP20_contract_info,
    CurrenciesNetworkName.TRX: TRC20_contract_info,
    CurrenciesNetworkName.ETC: ETC_ERC20_contract_info,
    CurrenciesNetworkName.FTM: opera_ftm_contract_info,
    CurrenciesNetworkName.MATIC: polygon_ERC20_contract_info,
    CurrenciesNetworkName.AVAX: avalanche_ERC20_contract_info,
    CurrenciesNetworkName.ONE: harmony_ERC20_contract_info,
    CurrenciesNetworkName.ARB: arbitrum_ERC20_contract_info,
    CurrenciesNetworkName.TON: ton_contract_info,
    CurrenciesNetworkName.SONIC: sonic_ERC20_contract_info,
    CurrenciesNetworkName.SOL: sol_contract_info,
    CurrenciesNetworkName.BASE: BASE_ERC20_contract_info
}


def get_contract_info(currency, network, blockchain_network='mainnet', contract_address=None, return_default=True):
    """ Return contract info for (currency, network) """
    contract_address_info = CONTRACT_INFO.get(network, {f'{blockchain_network}': {}}).get(f'{blockchain_network}').get(
        currency, {})
    if contract_address_info is None:
        return
    if 'address' not in contract_address_info:
        # If we provide contract address return info corresponding to that address
        if contract_address is not None:
            return contract_address_info.get(contract_address)
        if return_default:
            # If structure is to have default layer this return the default value easily
            if ca_info := contract_address_info.get('default') is not None:
                return ca_info
            # If structure is to use array this return field which set default in it.
            for ca, ca_info in contract_address_info.items():
                if ca_info.get('default', False):
                    return ca_info
    return contract_address_info
