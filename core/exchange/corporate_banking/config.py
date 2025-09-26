from django.conf import settings

from exchange.settings import secret_string

COBANK_TOMAN_CLIENT_ID = (
    secret_string(
        'gAAAAABnk2r0f3JZt8-bvmDwT8OOjawRvggN4I6bm9OzRsvcfuceo6IVU8eRcdM3wU9IRdGBEMEWifyK4NQO-07BZeYGk2PEGlnF3OtvzyRg2cHmGQ3AHEJjCENWAfER3ubLSRgXQKRk'
    )
    if settings.IS_PROD
    else 'yQ3e32SeIyfqQb'
)
COBANK_TOMAN_CLIENT_SECRET = (
    secret_string(
        'gAAAAABnk35EUAWsh3lysSjdoGMbQx5Et4hKv1SBJaADvAFMxra3LYVspzaStIqPvbIAZ88lhxU179QgFEIhmcBy7dcOUIIUvwcTu710R3Kpwsh-u580kd5ZDATKg6N4Hn4wUYdksGa94ttcyfYvQ1jehSqyfuQjJTSrOcCJs7mNOtfC9i9WbYlUsjhd4Bw8joJU_pnlOyMbK5W3Fy-zUmlRk4HhQzxu_ej7gTS0LGOwQqQ6kwfgWmJmjCCr0YOmjV3ZiHJWdaHS'
    )
    if settings.IS_PROD
    else 'asd6G%vc@134'
)
COBANK_TOMAN_USERNAME = (
    secret_string(
        'gAAAAABnk2y-XEeC_3tqx4J9IxGYMxDmzu7eZFTCPzVKQpzeMs57Y7rtV4JwjCgN9zbexDGxjtbJp9-M4-8w-kEX4bNu1MzAXw=='
    )
    if settings.IS_PROD
    else 'omcDDZ#!3'
)
COBANK_TOMAN_PASSWORD = (
    secret_string(
        'gAAAAABnk2zTsfm3ffnfpgptb9MhBPiZ0JEWZWZWRD3XmT2vGdoTjGycuCFRd_7mpBVFXUaBZTVMy_gc3dZFDHabWWSqghXCh6QcJ1KGaY35dn-1HsiJ7sDxBDbbWPHuyJEm64LwFDAh'
    )
    if settings.IS_PROD
    else '#$sdfgs423$#&vS'
)

RETRY_GET_TOKEN_COUNTDOWN = 30
RETRY_GET_TOKEN_RETRIES = 4

COBANK_JIBIT_API_KEY = (
    secret_string(
        'gAAAAABnrH7i3DRLZwQNa4ZhBLBT0H1W6mUEfetsXJjhQNI74iuK4o1ut5w27HFSN9lYjyeHTzO8JybLWKaNEY4P4e4IxC3w7dLQ5u-XGY2SNZPk3vWKl168PMn-kBqaYH6G-0yY9lIe',
    )
    if settings.IS_PROD
    else 'Dzgo2#1k958cz'
)
COBANK_JIBIT_SECRET_KEY = (
    secret_string(
        'gAAAAABnrH96bJJc2gOTCCkny5nytrqlxbR_NEh1-OSGNkShQbb5MAZ45eSlGsn0LkZoClCrATML56t-htM6FoXHI6hJN83_d6zcL7R5ItZ8ofoe5rXMAH-_4ei8Gw0cbtQAbRVlbKWl',
    )
    if settings.IS_PROD
    else 'asdq457GJ123##!'
)
