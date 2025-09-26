## Update submodule

```angular2html
git checkout master
git submodule update --init --recursive
```

## Install requirements

```shell
pip install -r requirements/[choose required file].txt
```

## Create DB

```postgresql
CREATE DATABASE [DB_NAME];
CREATE USER [USERNAME] WITH PASSWORD '[USERNAMEPASS]';
GRANT ALL PRIVILEGES ON DATABASE [DB_NAME] TO [USERNAME];
```

## Migrate

```
python manange.py migrate
```

## Collect static files

```shell
python manage.py collectstatic
```

## Create user and API key

```python
from exchange.explorer.accounts.models import User
from exchange.explorer.authentication.models import UserAPIKey

new_user = User.objects.create_user(username='new_user', email='user_email', password='user_password')
new_api_key = UserAPIKey.objects.create_key(name='new_api_key', user=new_user, rate='100/min')[1]

```

## Generate valid MASTERKEY

```python
from cryptography.fernet import Fernet

master_key = Fernet.generate_key().decode()
```

## Encrypt and decrypt secret strings

```python
from exchange.settings.secret import decrypt_string, encrypt_string

secret_string = 'explorer'
encrypted_string = encrypt_string(secret_string) # 'gAAAAABmL7-Nl-Hm8YC4MhT8kEAVwhBpWA-VgecbIO2RMm0Fx9wZ4ymDAssrirI0qwnoOcFDqdukzgRYiEMUxlMLS1fIpfsnAA=='
decrypted_string = decrypt_string(encrypted_string) # 'explorer'
```

## Run crons

```shell
python manage.py runcrons path.to.cron.class
```

## Run get block txs loop

```shell
python manage.py getblocktxs --network <network> --sleep <sleep>
```

## OS Packages

```commandline
sudo apt-get install gettext
```

## Language Controling

### To get appropreate response by your language, set `lang` in query param requests

```commandline
http://127.0.0.1:8000/accounts/dashboard?lang=fa
```

### To get list of languages you can use below api

```commandline
{{baseUrl}}/languages?
```

## Load providers from the code into DB

```shell
python manage.py loadproviders
```

## Load base urls from the code into DB

```shell
python manage.py loadbaseurls
```

## Set provider as default

```shell
python manage.py setdefaultprovider
```

## Set URL as default

```shell
python manage.py setdefaulturl
```

## Read transaction data from DB by hash

```shell
python manage.py readtx
```

## Read the latest cronjob log from DB

```shell
python manage.py readcronlog
```

## Set latest processed block for a network

```shell
python manage.py setlatestblock
```