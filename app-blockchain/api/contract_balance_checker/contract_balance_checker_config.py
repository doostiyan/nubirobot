from pydantic import BaseModel

from exchange.base.models import Currencies


class NetworkConfig(BaseModel):
    contract_address: str
    base_url_all_currencies: list
    base_url_selected_currencies: list
    symbol: str
    main_token: str
    precision: int
    currency: int
    network: str


class BalanceCheckerConfig:
    ETH = NetworkConfig(
        contract_address='0x0D2CEC5bc849a815b95539D970CFFfd4450db25A',
        base_url_all_currencies=[
            'https://mainnet.infura.io/v3/ae4824028c464b9c882e0e98476e5e23',
            'https://mainnet.infura.io/v3/fa39e950b293489682d2b61aadc27ce7',
            'https://mainnet.infura.io/v3/9a3232615858434ba4a89bc1ae5d8826',
            'https://ethereum-rpc.publicnode.com',
            'https://eth.llamarpc.com'
        ],
        base_url_selected_currencies=[
            'https://mainnet.infura.io/v3/9d4b78edc9ae45d5b18294eb7db804a8',
            'https://twilight-falling-patron.quiknode.pro/f33a52e0cd76f0017e576f9cbdf1367cd03a19f9',
        ],
        symbol='ETH',
        main_token='0x0000000000000000000000000000000000000000',
        precision=18,
        currency=Currencies.eth,
        network='ETH'
    )
    TRON = NetworkConfig(
        contract_address='TYtbShnGWyxdLYEqxJcVyZ7PvAu55oa7CP',
        base_url_all_currencies=['https://nodes6.nobitex1.ir/trx-fullnode/wallet'],
        base_url_selected_currencies=['https://nodes6.nobitex1.ir/trx-fullnode/wallet'],
        symbol='TRX',
        main_token='T9yD14Nj9j7xAB4dbGeiX9h8unkKHxuWwb',
        precision=6,
        currency=Currencies.trx,
        network='TRX'
    )
    POL = NetworkConfig(
        contract_address='0x0D2CEC5bc849a815b95539D970CFFfd4450db25A',
        base_url_all_currencies=['https://polygon-mainnet.infura.io/v3/9a3232615858434ba4a89bc1ae5d8826'],
        base_url_selected_currencies=['https://polygon-mainnet.infura.io/v3/9a3232615858434ba4a89bc1ae5d8826'],
        symbol='POL',
        main_token='0x0000000000000000000000000000000000000000',
        precision=18,
        currency=Currencies.pol,
        network='MATIC'
    )
    ARB = NetworkConfig(
        contract_address='0x0D2CEC5bc849a815b95539D970CFFfd4450db25A',
        base_url_all_currencies=['https://arbitrum-mainnet.infura.io/v3/f427e276abc34697ace352c95d8da4ab'],
        base_url_selected_currencies=['https://arbitrum-mainnet.infura.io/v3/f427e276abc34697ace352c95d8da4ab'],
        symbol='ETH',
        main_token='0x0000000000000000000000000000000000000000',
        precision=18,
        currency=Currencies.eth,
        network='ARB'
    )

    BSC = NetworkConfig(
        contract_address='0x0D2CEC5bc849a815b95539D970CFFfd4450db25A',
        base_url_all_currencies=[
            'https://bsc-mainnet.infura.io/v3/dc11b9b9de1842ca82af083d8a4c4088',
            'https://bsc-mainnet.infura.io/v3/f0c454211b7d4873bdbf6578695266e0',
            'https://bsc-mainnet.infura.io/v3/f427e276abc34697ace352c95d8da4ab',
            'https://bsc-rpc.publicnode.com',
            'https://bsc-mainnet.core.chainstack.com/49f83ff5bfc2a2c84de61cef35fa4362'
        ],
        base_url_selected_currencies=[
            'https://bsc-mainnet.infura.io/v3/5ac83bcdbe5b47c881c2c840a5e5437e',
            'https://binance.llamarpc.com',
        ],
        symbol='BNB',
        main_token='0x0000000000000000000000000000000000000000',
        precision=18,
        currency=Currencies.bnb,
        network='BSC'
    )
    AVAX = NetworkConfig(
        contract_address='0x0D2CEC5bc849a815b95539D970CFFfd4450db25A',
        base_url_all_currencies=['https://avalanche-mainnet.infura.io/v3/9a3232615858434ba4a89bc1ae5d8826'],
        base_url_selected_currencies=['https://avalanche-mainnet.infura.io/v3/9a3232615858434ba4a89bc1ae5d8826'],
        symbol='AVAX',
        main_token='0x0000000000000000000000000000000000000000',
        precision=18,
        currency=Currencies.avax,
        network='AVAX'
    )
    FTM = NetworkConfig(
        contract_address='0x578f6bdb36ebff94339e07c6be3e5c69d57dba9a',
        base_url_all_currencies=['https://fantom-mainnet.g.alchemy.com/v2/Ab1FUffKP5KUguxyNB3LhO3tHg38f6pl'],
        base_url_selected_currencies=['https://fantom-mainnet.g.alchemy.com/v2/Ab1FUffKP5KUguxyNB3LhO3tHg38f6pl'],
        symbol='FTM',
        main_token='0x0000000000000000000000000000000000000000',
        precision=18,
        currency=Currencies.ftm,
        network='FTM'
    )
    ETC = NetworkConfig(
        contract_address='0x0D2CEC5bc849a815b95539D970CFFfd4450db25A',
        base_url_all_currencies=['https://etc.rivet.link/'],
        base_url_selected_currencies=['https://etc.rivet.link/'],
        symbol='ETC',
        main_token='0x0000000000000000000000000000000000000000',
        precision=18,
        currency=Currencies.etc,
        network='ETC'
    )
    ONE = NetworkConfig(
        contract_address='0xfd6687f3231a8314229e600cc90025a3f9acf0c1',
        base_url_all_currencies=['https://api.harmony.one'],
        base_url_selected_currencies=['https://api.harmony.one'],
        symbol='ONE',
        main_token='0x0000000000000000000000000000000000000000',
        precision=18,
        currency=Currencies.one,
        network='ONE'
    )
    SONIC = NetworkConfig(
        contract_address='0x0D2CEC5bc849a815b95539D970CFFfd4450db25A',
        base_url_all_currencies=['https://rpc.soniclabs.com'],
        base_url_selected_currencies=['https://rpc.soniclabs.com'],
        symbol='S',
        main_token='0x0000000000000000000000000000000000000000',
        precision=18,
        currency=Currencies.s,
        network='SONIC'
    )
    Base = NetworkConfig(
        contract_address='0x0D2CEC5bc849a815b95539D970CFFfd4450db25A',
        base_url_all_currencies=['https://base-rpc.publicnode.com'],
        base_url_selected_currencies=['https://base-rpc.publicnode.com'],
        symbol='ETH',
        main_token='0x0000000000000000000000000000000000000000',
        precision=18,
        currency=Currencies.eth,
        network='BASE'
    )
