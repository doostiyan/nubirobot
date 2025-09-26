Code Review
===========

Transactions
------------

    This module provides exploring services for transactions performed in different blockchain networks.

Transaction Details Service
+++++++++++++++++++++++++++

    The get_transaction_details_dto method returns the details DTO of data returned by _get_transaction_details_data method for a transaction performed on blockchain. _get_transaction_details_data method first get the related inspector from get_inspector method and then it will check if there is config to use blockchain explorer or not then it will call the related method of inspector to get the transaction details data. If no transaction details data was found TransactionNotFoundException will be raised.

.. code-block:: python

    class TransactionExplorerService:

    @staticmethod
    def get_transaction_details_dto(network: str, tx_hash: str, currency: str = None, ) -> TransactionDetailsDTO:
        transaction_details_data = TransactionExplorerService._get_transaction_details_data(network, tx_hash)
        return TransactionDetailsDTOCreator.get_dto(transaction_details_data)

    @staticmethod
    
    def _get_transaction_details_data(network: str, tx_hash: str):

        _, network = parse_currency2code_and_symbol(network)
        inspector = get_inspector(network)
        network = network.upper()
        transaction_details_data = inspector.get_transaction_details(network, tx_hash)
        if transaction_details_data:
            return transaction_details_data
        else:
            raise TransactionNotFoundException(
                'Transaction not found, please check the network and hash parameter.')






Wallets
-------

    This module provides exploring services for wallets(addresses) in different blockchain networks.
    
    
Wallet Balance Service
++++++++++++++++++++++

    The get_wallet_balances_dto method returns the balance DTO of a wallet(address). It first calls _get_wallet_balance_data. It gets inspector based whether network is in MAIN_INSPECTORS and currency is main currency of network or not and then it will call its get_wallet_balances method. The results passes to _parse_wallet_balances_data that creates wallet balances DTO of it. Then the dto will be returned.
    
.. code-block:: python

     class WalletExplorerService:

    @staticmethod
    def get_wallet_balances_dto(network, address, currency):

        currency2parse = get_currency2parse(currency, network.lower())
        parsed_currency, currency_symbol = parse_currency2code_and_symbol(currency2parse)

        raw_balances_data = WalletExplorerService._get_wallet_balances_data(network.lower(),
                                                                            address,
                                                                            currency,
                                                                            currency_symbol,
                                                                            parsed_currency)
        balances_dto = WalletExplorerService._parse_wallet_balances_data(raw_balances_data,
                                                                         currency,
                                                                         currency_symbol,
                                                                         currency2parse,
                                                                         parsed_currency)
        return balances_dto

    @staticmethod
    def _get_wallet_balances_data(network, address, currency, currency_symbol, parsed_currency):
        _, network = parse_currency2code_and_symbol(network)
        network_upper = network.upper()
        address_list = [address, ]
        inspector = get_inspector(network)
        if network not in MAIN_INSPECTORS or (currency and is_main_currency_of_network(currency_symbol, network)):
            raw_balances_data = inspector.get_wallet_balances(network_upper, address_list, parsed_currency)
        else:
            main_network = MAIN_INSPECTORS.get(network)
            main_inspector = get_inspector(main_network)
            raw_balances_data = main_inspector.get_wallet_balances(network_upper, address_list,
                                                                   parsed_currency) or defaultdict()
            if not currency:
                currency_balances_data = inspector.get_wallet_balances(network_upper, address_list, parsed_currency)
                if currency_balances_data:
                    raw_balances_data.update({parsed_currency: currency_balances_data})
                else:
                    raise CustomException('An error occurred!')
        return raw_balances_data

    @staticmethod
    def _parse_wallet_balances_data(raw_balances_data, currency, currency_symbol, currency2parse, parsed_currency):
        if raw_balances_data:
            if isinstance(raw_balances_data, defaultdict):
                balances_data = []
                if currency:
                    if parsed_currency in raw_balances_data:
                        balance_data = raw_balances_data.get(parsed_currency)
                        if balance_data:
                            balance_data = balance_data[0]
                            balance_data['currency'] = currency_symbol
                            balances_data.append(balance_data)
                else:
                    for _currency, balance_data in raw_balances_data.items():
                        balance_data[0]['currency'] = get_currency_codename(_currency).upper()
                        balances_data.append(balance_data[0])
            elif isinstance(raw_balances_data, list):
                raw_balances_data[0]['currency'] = currency2parse
                balances_data = [raw_balances_data[0], ]
            elif isinstance(raw_balances_data, dict):
                raw_balances_data['currency'] = currency2parse
                balances_data = [raw_balances_data, ]
            else:
                balances_data = raw_balances_data
            return [WalletBalanceDTOCreator.get_dto(balance_data) for balance_data in balances_data]
        else:
            raise CustomException('An error occurred!')



Wallet Transactions Service
+++++++++++++++++++++++++++

    The get_wallet_transactions_dto method returns the balance DTO of a wallet(address). It first calls _get_wallet_transactions_data. It gets inspector based whether network is in MAIN_INSPECTORS and currency is main currency of network or not and then it will call its get_wallet_transactions method. The results passes to _parse_wallet_transactions_data that creates wallet transactions DTO of it. Then the dto will be returned.
    
.. code-block:: python
    
    @staticmethod
    def get_wallet_transactions_dto(network, address, currency):
        currency2parse = get_currency2parse(currency, network.lower())
        parsed_currency, currency_symbol = parse_currency2code_and_symbol(currency2parse)
        raw_transactions_data = WalletExplorerService._get_wallet_transactions_data(network.lower(),
                                                                                    address,
                                                                                    currency,
                                                                                    currency_symbol,
                                                                                    parsed_currency)
        transactions_dto = WalletExplorerService._parse_wallet_transactions_data(raw_transactions_data, currency,
                                                                                 currency_symbol, currency2parse,
                                                                                 parsed_currency)
        return transactions_dto

    @staticmethod
    def _get_wallet_transactions_data(network, address, currency, currency_symbol, parsed_currency):
        _, network = parse_currency2code_and_symbol(network)
        network_upper = network.upper()
        inspector = get_inspector(network)
        if network not in MAIN_INSPECTORS or (currency and is_main_currency_of_network(currency_symbol, network)):
            raw_transactions_data = inspector.get_wallet_transactions(network_upper, address,
                                                                      parsed_currency)
        else:
            main_network = MAIN_INSPECTORS.get(network)
            main_inspector = get_inspector(main_network)
            raw_transactions_data = main_inspector.get_wallet_transactions(network_upper, address,
                                                                           parsed_currency) or defaultdict()
            if not currency:
                currency_transactions_data = inspector.get_wallet_transactions(network_upper, address, parsed_currency)
                if currency_transactions_data:
                    raw_transactions_data.update({parsed_currency: currency_transactions_data})
                else:
                    raise CustomException('An error occurred!')
        return raw_transactions_data

    @staticmethod
    def _parse_wallet_transactions_data(raw_transactions_data, currency, currency_symbol, currency2parse,
                                        parsed_currency):
        if raw_transactions_data is not None:
            transactions_data = []
            if isinstance(raw_transactions_data, (defaultdict, dict)):
                if currency:
                    if parsed_currency in raw_transactions_data:
                        raw_transaction_data = raw_transactions_data.get(parsed_currency)
                        if raw_transaction_data:
                            for transaction_data in raw_transaction_data:
                                if isinstance(transaction_data, dict):
                                    transaction_data['currency'] = currency_symbol
                                else:
                                    transaction_data.currency = currency_symbol
                                transactions_data.append(transaction_data)
                else:
                    for _currency, raw_transaction_data in raw_transactions_data.items():
                        currency_code_name = get_currency_codename(_currency).upper()
                        for transaction_data in raw_transaction_data:
                            if isinstance(transaction_data, dict):
                                transaction_data['currency'] = currency_code_name
                            else:
                                transaction_data.currency = currency_code_name
                            transactions_data.append(transaction_data)
            elif isinstance(raw_transactions_data, list):
                for transaction_data in raw_transactions_data:
                    if isinstance(transaction_data, dict):
                        transaction_data['currency'] = currency2parse
                    else:
                        transaction_data.currency = currency2parse
                    transactions_data.append(transaction_data)
            else:
                transactions_data = raw_transactions_data

            return [WalletTransactionDTOCreator.get_dto(transaction_data) for transaction_data in transactions_data]
        else:
            raise CustomException('An error occurred!')
            
            
Wallet Details Service
++++++++++++++++++++++

    This method calls two service above and returns the result as wallet details DTO.

.. code-block:: python

    @staticmethod
    def get_wallet_details_dto(network, address, currency):
        balances_dto = WalletExplorerService.get_wallet_balances_dto(network, address, currency)
        transactions_dto = WalletExplorerService.get_wallet_transactions_dto(network, address, currency)
        details_dto = WalletDetailsDto(address=address,
                                       network=network,
                                       balance=balances_dto,
                                       transactions=transactions_dto)
        return details_dto


API
---

It provides features about using API.

API key
+++++++

UserAPIKey is subclass of AbstractAPIKey of djangorestframework-api-key package that extended with rate and a foreign key to User model.

.. code-block:: python

    class UserAPIKey(AbstractAPIKey):
        objects = UserAPIKeyManager()
        user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_api_keys')
        rate = models.CharField(max_length=20)



This is the manager of model above. The get_from_key method trys to first fetch api key by its prefix from local cache then redis and then database. It will write to cache in the case of not written.

.. code-block:: python

    class UserAPIKeyManager(BaseAPIKeyManager):

        def _get_api_key_from_db(self, prefix: str):
            queryset = self.get_usable_keys()
            try:
                api_key = queryset.get(prefix=prefix)
                return api_key
            except self.model.DoesNotExist:
                raise APIKeyNotFoundException(
                    'Pass Valid API key in {} header'.format(settings.API_KEY_CUSTOM_HEADER_CLIENT_FORMAT),
                    'API key not found, Enter valid API key')

        def get_from_key(self, key: str) -> "UserAPIKey":
            prefix, _, _ = key.partition(".")

            api_key = CacheUtils.read_from_local_cache(prefix, 'local__user_api_keys')
            if not api_key:
                api_key = CacheUtils.read_from_external_cache(prefix, 'redis__user_api_keys')
                if not api_key:
                    api_key = self._get_api_key_from_db(prefix)
                    CacheUtils.write_to_external_cache(prefix, api_key, 'redis__user_api_keys')
                CacheUtils.write_to_local_cache(prefix, api_key, 'local__user_api_keys')

            if not api_key.is_valid(key):
                raise APIKeyNotFoundException(
                    'Pass Valid API key in {} header'.format(settings.API_KEY_CUSTOM_HEADER_CLIENT_FORMAT),
                    'API key not found, Enter valid API key')
            else:
                return api_key

        def is_valid(self, api_key) -> bool:
            if api_key.has_expired:
                return False

            return True

UserHasAPIKey permission is checked for transactions and wallets services. It receives keys either from cookie or header based on format be html or json. It always allows clients with ips declared in settings to use api by free and without passing API key and for others checks the validity of api_key by is_valid method of model manager.

.. code-block:: python

    class UserHasAPIKey(BaseHasAPIKey):
        model = UserAPIKey
        API_KEY_HEADER = settings.API_KEY_CUSTOM_HEADER

        def has_permission(self, request, view) -> bool:
            assert self.model is not None, (
                    "%s must define `.model` with the API key model to use"
                    % self.__class__.__name__
            )
            client_ip = get_client_ip(request)
            if client_ip in settings.ALLOWED_CLIENT_IPS:
                return True
            else:
                key = self.get_key(request)
                if not key:
                    return False
                model_manager = self.model.objects
                api_key = model_manager.get_from_key(key)
                request.api_key = api_key
                return model_manager.is_valid(api_key)

        @classmethod
        def get_key(cls, request):
            format = request.accepted_renderer.format
            if format == 'html':
                key = request.COOKIES.get('api_key')
            else:
                key = request.META.get(cls.API_KEY_HEADER)
            return key


JWT AUTHENTICATION
++++++++++++++++++

This is authentication class used for dashboard view. authenticate method first obtains token from cookies or header bases on format and then validate this token and returns authenticated user. It is stateless and does not require database queries.


.. code-block:: python

    class APIAuthentication(JWTStatelessUserAuthentication):
        def authenticate(self, request):
            format = request.accepted_renderer.format
            if format == 'html':
                raw_token_str = request.COOKIES.get('access_token')
                if raw_token_str:
                    raw_token = str.encode(raw_token_str)
                else:
                    return None
            else:
                header = self.get_header(request)
                if header is None:
                    return None
                raw_token = self.get_raw_token(header)
            if raw_token is None:
                return None

            validated_token = self.get_validated_token(raw_token)

            return self.get_user(validated_token), validated_token


Throttling
++++++++++

This is throttle class used for wallets and transactions services. allow_request method calls throttle_success or throttle_failure methods based on history and rate limit of api key.

.. code-block:: python

    class APIKeyRateThrottle(BaseThrottle):
        cache = caches['redis__throttling']
        cache_format = 'throttle_%(ident)s'
        timer = time.time

        def get_cache_key(self, request, view):
            return self.cache_format % {
                'ident': self.get_ident(request)
            }

        def get_ident(self, request):
            return request.api_key.prefix

        def get_rate(self, request):
            return request.api_key.rate

        def parse_rate(self, rate):
            """
            Given the request rate string, return a two tuple of:
            <allowed number of requests>, <period of time in seconds>
            """
            if rate is None:
                return None, None
            num, period = rate.split('/')
            num_requests = int(num)
            duration = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}[period[0]]
            return num_requests, duration

        def allow_request(self, request, view):
            """
            Implement the check to see if the request should be throttled.

            On success calls `throttle_success`.
            On failure calls `throttle_failure`.
            """
            if hasattr(request, 'api_key'):
                rate = self.get_rate(request)
                self.num_requests, self.duration = self.parse_rate(rate)

                self.key = self.get_cache_key(request, view)
                if self.key is None:
                    return True

                self.history = self.cache.get(self.key, [])
                self.now = self.timer()

                # Drop any requests from the history which have now passed the
                # throttle duration
                while self.history and self.history[-1] <= self.now - self.duration:
                    self.history.pop()
                if len(self.history) >= self.num_requests:
                    return self.throttle_failure()
                return self.throttle_success()
            return True

        def throttle_success(self):
            """
            Inserts the current request's timestamp along with the key
            into the cache.
            """
            self.history.insert(0, self.now)
            self.cache.set(self.key, self.history, self.duration)
            return True

        def throttle_failure(self):
            """
            Called when a request to the API has failed due to throttling.
            """
            return False

        def wait(self):
            """
            Returns the recommended next request time in seconds.
            """
            if self.history:
                remaining_duration = self.duration - (self.now - self.history[-1])
            else:
                remaining_duration = self.duration

            available_requests = self.num_requests - len(self.history) + 1
            if available_requests <= 0:
                return None

            return remaining_duration / float(available_requests)


Accounts
--------

This is the app that add accounting features to the project.

Login View
++++++++++

The post method first checks if the login_form is valid then authenticates the user by given credentials if it was successful checks the validity of refresh and access token and issues new pair tokens if required then redirects to the dashboard page.

.. code-block:: python

    class LoginView(APIView):
        renderer_classes = (JSONRenderer, TemplateHTMLRenderer,)

        def get(self, request, format=None):
            format = request.accepted_renderer.format
            if format == 'html':
                login_form = LoginForm()
                context = {'login_form': login_form}
                return render(request, 'accounts/login.html', context)

        def post(self, request):

            login_form = LoginForm(data=request.data)
            context = {'login_form': login_form}
            if login_form.is_valid():
                username = login_form.cleaned_data['username']
                password = login_form.cleaned_data['password']
                user = authenticate(username=username, password=password)
                if not user:
                    login_form.add_error("password", "خطا: نام کاربری یا گذرواژه اشتباه است!")
                    return render(request, 'accounts/login.html', context)

                access_token_str = request.COOKIES.get('access_token')
                response = redirect(reverse('accounts:dashboard') + '?format=html')
                issue_new_pair_tokens = False
                if not access_token_str or (access_token_str and has_expired(decode_token('access', access_token_str))):
                    refresh_token_str = request.COOKIES.get('refresh_token')
                    if refresh_token_str:
                        refresh_token = decode_token('refresh', refresh_token_str)
                        if has_expired(refresh_token):
                            issue_new_pair_tokens = True
                        else:
                            access_token = refresh_token.access_token
                            response.set_cookie('access_token', access_token, httponly=True)
                    else:
                        issue_new_pair_tokens = True
                if issue_new_pair_tokens:
                    refresh_token, access_token = get_token(user)
                    response.set_cookie('refresh_token', refresh_token, httponly=True)
                    response.set_cookie('access_token', access_token, httponly=True)

                return response

            return render(request, 'accounts/login.html', context)



Basis
-----

This is the app contains some basic templates and forms.

TableField
++++++++++

This is a field in a django form shown as html table. It accepts list of dictionaries as input and creates list of lists that the first list is headers and others are values. It is used in transactions and wallets apps.

.. code-block:: python

    class TableField(Field):
        widget = Table
        fields = None
        headers = None

        def __init__(self, *args, **kwargs):
            for kwarg in ['headers', 'fields']:
                if kwarg in kwargs:
                    value = kwargs.pop(kwarg)
                    setattr(self, kwarg, value)
            super().__init__(*args, **kwargs)

        def prepare_value(self, value):
            val = [[]]
            if self.headers:
                val = [self.headers]
            if value:
                if self.fields:
                    for i in range(len(value)):
                        value[i] = {field: value[i][field] for field in self.fields}

                val += list_of_dicts2list_of_lists(value)
            else:
                if self.headers:
                    val += [[''] * len(self.headers)]
            return val


Widget
******

This is table widget used in table field.

.. code-block:: python

    class Table(Widget):
        template_name = 'basis/table_field.html'

Html
****

This is html code of table field.

.. code-block::

    <div class="py-2 table-responsive">
        <table class="table table-striped table-bordered text-center" type="{{ widget.type }}"
                {% include "django/forms/widgets/attrs.html" %}>
            {% with widget.value|string2list as rows %}
                <thead>
                <tr>
                    {% for col in rows.0 %}
                        <th>{{ col }}</th>
                    {% endfor %}
                </tr>
                </thead>
                <tbody>
                {% for row in rows %}
                    {% if not forloop.first %}
                        <tr>
                            {% for col in row %}
                                <td dir="ltr">{{ col }}</td>
                            {% endfor %}
                        </tr>
                    {% endif %}
                {% endfor %}
                </tbody>
            {% endwith %}
        </table>
    </div>


Utils
-----

Here are some tools used in django apps.

DTO
+++

This is the parent class of DTO classes of apps. get_data method returns a dict representation of DTO data.

.. code-block:: python

    @dataclass
    class DTO:
        @classmethod
        def get_fields(cls):
            return fields(cls)

        def get_data(self):
            data = {}
            for field in self.get_fields():
                value = getattr(self, field.name)
                if isinstance(value, DTO):
                    value = value.get_data()
                elif isinstance(value, list):
                    for i in range(len(value)):
                        if isinstance(value[i], DTO):
                            value[i] = value[i].get_data()
                data[field.name] = value
            return data


Base DTO Creator
++++++++++++++++

This is the base class of DTO Creator classes of apps. get_dto method creates DTO using matched data between data given and DTO class fields.

.. code-block:: python

    class BaseDTOCreator:
        DTO_CLASS = None

        @classmethod
        def normalize_data(cls, data) -> dict:
            if isinstance(data, dict):
                return data
            else:
                return data.__dict__

        @classmethod
        def get_dto(cls, data: dict):
            normalized_data = cls.normalize_data(data)
            _fields = cls.DTO_CLASS.get_fields()
            matched_data = {field.name: normalized_data.get(field.name) for field in _fields}
            return cls.DTO_CLASS(**matched_data)
            
            
BaseInspector 
*************

This is wrapper for blockchain module BlockchainExplorer and Coins Inspector classes. It also saves the call to each inspector apis.

.. code-block:: python

	class BaseInspector:
	    network = None
	    transaction_details_api_methods: None
	    wallet_balances_api_methods: None
	    wallet_transactions_api_methods: None

	    @classmethod
	    @run_in_thread
	    @catch_all_exceptions()
	    def log_call(cls, selected_api):
		Call.objects.create(network=cls.network, api=selected_api)

	    @classmethod
	    def get_transaction_details(cls, network, tx_hash):
		if network in APIS_CONF and 'txs_details' in APIS_CONF[network]:
		    return cls.get_transaction_details_new_method(network, tx_hash)
		else:
		    return cls.get_transaction_details_old_method(tx_hash)

	    @classmethod
	    def get_wallet_balances(cls, network, address_list, parsed_currency):
		if network in APIS_CONF and 'get_balances' in APIS_CONF[network]:
		    return cls.get_wallet_balances_new_method({network: address_list}, parsed_currency)
		else:
		    return cls.get_wallet_balances_old_method(address_list=address_list)

	    @classmethod
	    def get_wallet_transactions(cls, network, address, parsed_currency):
		if network in APIS_CONF and 'get_txs' in APIS_CONF[network]:
		    return cls.get_wallet_transactions_new_method(network, address, parsed_currency)
		else:
		    return cls.get_wallet_transactions_old_method(address=address)

	    # old version (Currency inspectors) ...............................................................................
	    @classmethod
	    def get_transaction_details_old_method(cls, tx_hash):
		selected_api = cls.select_transaction_details_api_method()
		api_method = cls.transaction_details_api_methods[selected_api]
		cls.log_call(selected_api)
		return api_method(tx_hash)

	    @classmethod
	    def select_transaction_details_api_method(cls):
		raise NotImplementedError

	    @classmethod
	    def get_wallet_balances_old_method(cls, address_list):
		selected_api = cls.select_wallet_balances_api_method()
		api_method = cls.wallet_balances_api_methods[selected_api]
		cls.log_call(selected_api)
		return api_method(address_list)

	    @classmethod
	    def select_wallet_balances_api_method(cls):
		raise NotImplementedError

	    @classmethod
	    def get_wallet_transactions_old_method(cls, address):
		selected_api = cls.select_wallet_transactions_api_method()
		api_method = cls.wallet_transactions_api_methods[selected_api]
		cls.log_call(selected_api)
		return api_method(address)

	    @classmethod
	    def select_wallet_transactions_api_method(cls):
		raise NotImplementedError

	    # new version (BlockchainExplorer) .................................................................................

	    @classmethod
	    def get_transaction_details_new_method(cls, network, tx_hash):
		selected_api = cls.select_transaction_details_api_name()
		cls.log_call(selected_api)
		return BlockchainExplorer.get_transactions_details([tx_hash, ], network, selected_api, raise_error=True).get(
		    tx_hash)

	    @classmethod
	    def select_transaction_details_api_name(cls):
		return APIS_CONF[cls.network.upper()]['txs_details']

	    @classmethod
	    def get_wallet_balances_new_method(cls, address_list, parsed_currency):
		selected_api = cls.select_wallet_balances_api_name()
		cls.log_call(selected_api)
		return BlockchainExplorer.get_wallets_balance(address_list, parsed_currency, selected_api, raise_error=True)

	    @classmethod
	    def select_wallet_balances_api_name(cls):
		return APIS_CONF[cls.network.upper()]['get_balances']

	    @classmethod
	    def get_wallet_transactions_new_method(cls, address, parsed_currency, network):
		selected_api = cls.select_wallet_transactions_api_name()
		cls.log_call(selected_api)
		return BlockchainExplorer.get_wallet_transactions(address, parsed_currency, network, selected_api,
		                                                  raise_error=True)

	    @classmethod
	    def select_wallet_transactions_api_name(cls):
		return APIS_CONF[cls.network.upper()]['get_balances']

            

