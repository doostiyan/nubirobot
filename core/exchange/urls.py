""" Project URLS """
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.urls import include, path, re_path
from django.views.decorators.cache import cache_control
from django.views.generic.base import RedirectView, TemplateView
from rest_framework import routers

from exchange.accounting.views import deposit_system_bank_account
from exchange.accounts.views import anti_phishing as anti_phishing_views
from exchange.accounts.views import auth as auth_views
from exchange.accounts.views import captcha as captcha_views
from exchange.accounts.views import internal as internal_accounts
from exchange.accounts.views import merge as merge_views
from exchange.accounts.views import otp as otp_views
from exchange.accounts.views import profile as profile_views
from exchange.accounts.views import referral as referral_views
from exchange.accounts.views import userplan as userplan_views
from exchange.accounts.views.restriction import UserRestrictionView
from exchange.android import views as android_views
from exchange.apikey import views as apikey
from exchange.asset_backed_credit.api import views as abc_views
from exchange.base import views as base_views
from exchange.blockchain import views as blockchain
from exchange.captcha.views import captcha_image as captcha_image_views
from exchange.charts import urls as charts_urls
from exchange.corporate_banking.api import views as corporate_banking
from exchange.credit import views as credit
from exchange.crm import views as crms
from exchange.direct_debit.api import views as direct_debit
from exchange.earn import views as earn
from exchange.features.views import get_request_status, register_request_in_queue
from exchange.gift import views as gift
from exchange.gift.postal_order_views import get_padro_province_cities, get_padro_provinces
from exchange.margin import views as margin
from exchange.market import coinmarketcap
from exchange.market import udf as market_udf
from exchange.market import views as market
from exchange.marketing.api.views import referral
from exchange.marketing.api.views import user_suggestion as marketing
from exchange.marketing.api.views.campaign import (
    CampaignInfoRequestView,
    CampaignJoinRequestView,
    CampaignRewardCapacityView,
    CampaignRewardRequestView,
)
from exchange.marketing.api.views.otp import CampaignOTPRequestView, CampaignOTPVerifyView
from exchange.metrics import views as metrics
from exchange.notification.api import views as notification
from exchange.oauth.api import views as oauth
from exchange.oauth.api.services import views as oauth_services
from exchange.pool import views as pool
from exchange.portfolio.views import (
    get_daily_total_balance,
    last_month_total_profit,
    last_week_daily_profit,
    last_week_daily_total_profit,
)
from exchange.pricealert import views as pricealert
from exchange.promotions import views as promotions
from exchange.recovery import views as recovery
from exchange.redeem import views as redeem
from exchange.report.views import status as status_report
from exchange.report.views import views as report
from exchange.security import views as security
from exchange.security.views.address_book import (
    DeleteAddressBookView,
    ListCreateAddressBookView,
    activate_whitelist,
    deactivate_whitelist,
)
from exchange.shetab import urls as shetab_urls
from exchange.shetab import views as shetab
from exchange.socialtrade import views as social_trade
from exchange.staking import views as staking
from exchange.support import views as support
from exchange.support.views import get_next_call_reason_url
from exchange.system.views import ListBotTransactionView
from exchange.ticketing import views as ticketing
from exchange.wallet import views as wallet
from exchange.wallet.internal.views import (
    internal_batch_transaction_view,
    internal_bulk_transfer_view,
    internal_list_wallets_view,
    internal_withdraw_rial_view,
)
from exchange.web_engage.api.views.discount import (
    CheckActiveUserDiscountApi,
    CreateUserDiscountApi,
    SendExternalDiscountApi,
)
from exchange.web_engage.api.views.esp import ESPDeliveryStatusApi, ESPMessageApi
from exchange.web_engage.api.views.ssp import SSPMessageApi
from exchange.ws.views import healthcheck_ws_publish, ws_status
from exchange.xchange import views as xchange

router = routers.DefaultRouter()
admin.site.site_header = 'Nobitex Admin'
admin.site.site_title = 'Nobitex Admin'
urlpatterns = [
    # Base
    path('', base_views.home),
    path('base/ntp', base_views.ntp),

    # CRM
    path('crm/news/list', crms.NewsList.as_view()),
    path('crm/news/tags/list', crms.NewsTags.as_view()),

    # Health Checks
    path('check/connectivity', base_views.connectivity),
    path('check/token', base_views.check_token),
    path('check/version', base_views.check_version),
    path('check/debug', base_views.check_debug),
    path('check/health', base_views.check_health),

    # v2
    path('v2/options', profile_views.v2_options),
    path('v2/depth/<str:symbol>', market.DepthChartAPI.as_view()),
    path('v2/orderbook', market.v2_orderbook),  # Deprecated
    path('v2/orderbook/<str:symbol>', market.OrderBookV2.as_view()),
    path('v2/trades', market.v2_trades),  # Deprecated
    path('v2/trades/<str:symbol>', market.v2_trades_get),
    path('v2/crypto-prices', market.v2_crypto_prices),
    # v3
    path('v3/orderbook/<str:symbol>', market.OrderBookV3.as_view()),

    # Market
    path('market/orders/list', market.orders_list),
    path('market/orders/open-count', market.OpenOrderCountView.as_view()),
    path('market/orders/add', market.OrderCreateView.as_view()),
    path('market/orders/batch-add', market.OrderBatchCreateView.as_view()),
    path('market/orders/estimate', market.orders_estimate),
    path('market/orders/status', market.orders_status),
    path('market/orders/cancel-old', market.orders_cancel_old),
    path('market/orders/cancel-batch', market.orders_cancel_batch),
    path('market/orders/update-status', market.orders_update_status),
    path('market/stats', market.market_stats),
    path('market/global-stats', market.market_global_stats),
    path('market/trades/list', market.trades_list),
    path('market/usd-value', market.usd_value),

    # Market Chart (UDF)
    path('market/udf/config', market_udf.udf_config),
    path('market/udf/symbols', market_udf.udf_symbols),
    path('market/udf/search', market_udf.udf_search),
    path('market/udf/history', market_udf.UDFHistory.as_view()),
    path('market/udf/time', market_udf.udf_time),
    path('market/udf/quotes', market_udf.udf_quotes),
    path('charts/storage/1.1/', include(charts_urls)),


    # Marketing
    path('marketing/suggestion-category/list', marketing.suggestion_category_list),
    path('marketing/suggestion/add', marketing.add_user_suggestion),
    path('marketing/campaign', CampaignInfoRequestView.as_view()),
    path('marketing/campaign/join', CampaignJoinRequestView.as_view()),
    path('marketing/campaign/reward', CampaignRewardRequestView.as_view()),
    path('marketing/campaign/reward/capacity', CampaignRewardCapacityView.as_view()),
    path('marketing/campaign/referral', referral.ReferralCampaign.as_view()),
    path('marketing/campaign/otp', CampaignOTPRequestView.as_view()),
    path('marketing/campaign/otp/verify', CampaignOTPVerifyView.as_view()),
    path('marketing/campaign/webengage/discount/external', SendExternalDiscountApi.as_view()),

    # Margin
    path('margin/markets/list', margin.MarginMarketListView.as_view()),
    path('margin/fee-rates', margin.MarginFeeRatesListView.as_view()),
    path('margin/orders/add', margin.MarginOrderCreateView.as_view()),
    path('margin/delegation-limit', margin.MarginDelegationLimitView.as_view()),
    path('margin/calculator/<str:mode>', margin.MarginCalculatorView.as_view()),
    path('margin/predict/<str:category>', margin.MarginPredictView.as_view()),
    path('positions/list', margin.PositionsListView.as_view()),
    path('positions/active-count', margin.ActivePositionsCountView.as_view()),
    path('positions/<int:pk>/status', margin.PositionStatusView.as_view()),
    path('positions/<int:pk>/close', margin.PositionCloseView.as_view()),
    path('positions/<int:pk>/edit-collateral/options', margin.PositionCollateralEditOptionsView.as_view()),
    path('positions/<int:pk>/edit-collateral', margin.PositionCollateralEditView.as_view()),

    # Special Tradings
    path('market/autotrade/get-options', market.autotrade_get_options),
    path('market/autotrade/set-options', market.autotrade_set_options),

    # User Profile
    path('users/preferences', profile_views.users_preferences),
    path('users/set-preference', profile_views.users_set_preference),
    path('users/profile', profile_views.users_profile),
    path('users/limitations', profile_views.users_limitations),
    path('users/profile-edit', profile_views.users_profile_edit),
    path('users/cards-add', profile_views.users_cards_add),
    path('users/cards-delete', profile_views.users_cards_delete),
    path('users/accounts-add', profile_views.users_accounts_add),
    path('users/payment-accounts-add', profile_views.users_payment_accounts_add),
    path('users/accounts-delete', profile_views.users_accounts_delete),
    path('users/verify', profile_views.users_verify),
    path('users/verify-email', profile_views.users_verify_email),
    path('users/verify-mobile', profile_views.users_verify_mobile, name='verify-mobile'),
    path('users/verify-phone', profile_views.users_verify_phone),
    path('users/reset-verification', profile_views.users_reset_verification),
    path('users/verification/status', profile_views.verification_status),
    path('users/upload-file', profile_views.upload_file),
    path('users/set-national-serial-number', profile_views.users_national_serial_add),
    path('users/verification/liveness', profile_views.users_update_verification_result),
    path('users/rejection-reason', profile_views.user_level_up_rejection_reasons, name='rejection_reason_url'),
    path('users/upgrade/level3', profile_views.users_upgrade_level3),
    # User restrictions
    path('users/restrictions', UserRestrictionView.as_view()),

    # User Merge
    path('users/create-merge-request', merge_views.CreateMergeRequestView.as_view()),
    path('users/verify-merge-request', merge_views.VerifyMergeRequestView.as_view()),

    # Users markets preferences
    path('users/markets/favorite', market.UsersFavoriteMarkets.as_view()),
    path('users/markets/favorite/list', market.UsersFavoriteMarkets.as_view()),

    # accounting
    path('accounting/system/deposits', deposit_system_bank_account),

    # call_reason api urls
    path('users/call-reason/get-next-url', get_next_call_reason_url, name='call_reason_get_next_url'),

    # User Telegram Connection
    path('users/telegram/generate-url', profile_views.telegram_generate_start_url),
    path('users/telegram/set-chat-id', profile_views.telegram_set_chat_id),
    path('users/telegram/reset-chat-id', profile_views.telegram_reset_chat_id),

    # User Notifications
    path('notifications/list', profile_views.notifications_list),
    path('notifications/read', profile_views.notifications_read),
    path('v2/notifications/list', notification.notifications_list),
    path('v2/notifications/read', notification.notifications_read),

    # User Referrals
    path('users/get-referral-code', referral_views.users_get_referral_code),
    path('users/set-referrer', referral_views.users_set_referrer),
    path('users/referral/referral-status', referral_views.users_referral_status),
    path('users/referral/set-referrer', referral_views.users_set_referrer),
    path('users/referral/links-add', referral_views.users_referral_links_add),
    path('users/referral/links-list', referral_views.users_referral_links_list),

    # User Plans
    path('users/plans/activate', userplan_views.activate_plan),
    path('users/plans/deactivate', userplan_views.deactivate_plan),
    path('users/plans/list', userplan_views.plans_list),
    path('users/plans/developer2021', userplan_views.plans_developer2021),

    # User Wallets
    path('v2/wallets', wallet.v2_wallets),
    path('users/wallets/list', wallet.wallets_list),
    path('users/wallets/balance', wallet.wallets_balance),
    path('users/wallets/transactions/list', wallet.wallets_transactions_list),
    path('users/wallets/deposits/list', wallet.wallets_deposits_list),
    path('users/wallets/deposits/refresh', wallet.wallets_deposits_refresh),
    path('users/wallets/deposit/bank', wallet.wallets_deposit_bank),
    path('users/wallets/deposit/shetab', wallet.wallets_deposit_shetab),
    path('users/wallets/deposit/', include(shetab_urls)),
    path('users/wallets/deposit/update', staff_member_required(wallet.UpdateDepositWallet.as_view())),
    path('users/wallets/generate-address', wallet.wallets_generate_address),
    path('users/wallets/invoice/generate', wallet.wallets_ln_invoice_create),
    path('users/wallets/invoice/decode', wallet.wallets_decode_invoice),
    path('withdraws/<int:withdraw>', wallet.withdraws_get),
    path('withdraws/<int:withdraw>/update-status', wallet.withdraws_update_status),
    path('users/wallets/withdraw', wallet.wallets_withdraw),
    path('users/wallets/withdraw-confirm', wallet.wallets_withdraw_confirm),
    path('users/wallets/withdraw-cancel', wallet.wallets_withdraw_canceled),
    path('users/wallets/withdraws/list', wallet.wallets_withdraws_list),
    path('users/wallets/convert', wallet.wallets_convert),
    path('users/transactions-history', wallet.user_transaction_history),
    path('wallets/transfer', wallet.TransferBalance.as_view()),
    path('wallets/bulk-transfer', wallet.BulkTransferBalance.as_view()),
    path('wallets/bulk-transfers/list', wallet.WalletBulkTransferRequestsListView.as_view()),
    path('users/wallets/withdraws/receipt', wallet.internal_transfer_receipt),
    path('users/transactions-histories/request', wallet.TransactionHistoryView.as_view()),
    path('users/transactions-histories/<int:pk>/download', wallet.download_user_transaction_history),

    path('users/payments/create-id', shetab.user_payments_ids_create),
    path('users/payments/ids-list', shetab.user_payments_ids_list),
    path('users/payments/callback', shetab.user_payments_callback),

    # User Portfolio
    path('users/portfolio/last-week-daily-profit', last_week_daily_profit),
    path('users/portfolio/last-week-daily-total-profit', last_week_daily_total_profit),
    path('users/portfolio/last-month-total-profit', last_month_total_profit),
    path('users/portfolio/daily_total_balance', get_daily_total_balance),

    # Security
    path('security/emergency-cancel/', security.EmergencyCancelWithdraw.as_view(), name='emergency_cancel'),
    path('security/emergency-cancel/get-code', security.emergency_cancel_withdraw_get_code),
    path('security/emergency-cancel/activate', security.emergency_cancel_withdraw_activate),
    path('security/devices', security.user_devices),
    path('security/devices/delete', security.delete_device),
    path('security/devices/delete-all', security.delete_all_devices),
    path('security/anti-phishing', anti_phishing_views.AntiPhishingView.as_view()),
    path('address_book', ListCreateAddressBookView.as_view(), name='address_book_list_create'),
    path('address_book/<int:pk>/delete', DeleteAddressBookView.as_view(), name='address_book_delete'),
    path('address_book/whitelist/activate', activate_whitelist, name='activate_whitelist'),
    path('address_book/whitelist/deactivate', deactivate_whitelist, name='deactivate_whitelist'),
    # Features
    path('users/feature/add-request/<str:feature>', register_request_in_queue),
    path('users/feature/request-status/<str:feature>', get_request_status),

    # Webhooks
    path('webhooks/hot/new-tx/btc', wallet.btc_blockcypher_webhook),
    path('webhooks/hot/e7rSvUIrFsGK9zJxtUz4vyLr/hot_wallet_creation/', wallet.hot_wallet_creation),
    path('webhook/ltc/zhCuWyFjZFsGK9zuDTBZBhPuo/', wallet.ltc_blockcypher_webhook, name='ltc_blockcypher_webhook'),
    path('webhook/doge/zhCuWyFjZFsGK9zuDTBZBhPuo/', wallet.doge_blockcypher_webhook, name='ltc_blockcypher_webhook'),
    path('webhook/btc/YrftjS9zPuFmSVNAdZvJxtUz4/', wallet.btc_blocknative_webhook, name='btc_blocknative_webhook'),
    path('webhook/eth/YrftjS9zPuFmSVNAdZvJxtUz4/', wallet.eth_blocknative_webhook, name='eth_blocknative_webhook'),
    path('webhook/xrp/vyLrbcYBjJ89uH2FrrZhfnHdq/', wallet.xrpl_webhook, name='xrp_webhook'),

    # OTP
    path('otp/request', otp_views.otp_request),
    path('otp/request-public', otp_views.otp_request_public),
    path('users/tfa/request', otp_views.users_tfa_request),
    path('users/tfa/confirm', otp_views.users_tfa_confirm),
    path('users/tfa/disable', otp_views.users_tfa_disable),

    # Xchange
    path('exchange/options', xchange.options),
    path('exchange/get-quote', xchange.get_quote),
    path('exchange/create-trade', xchange.create_trade),
    path('exchange/get-trade', xchange.get_trade),
    path('exchange/trade-histories', xchange.trades_history),
    path('exchange/convert-small-assets', xchange.convert_small_assets),

    # Price Alert
    path('v2/price-alerts', pricealert.PricerAlertsView.as_view()),

    # Promotions
    path('promotions/discount/trades-history', promotions.get_history_trades_for_user_discount_api),
    path('promotions/discount/transactions-history', promotions.get_history_discount_transaction_log_api),
    path('promotions/discount/discount-history', promotions.get_user_discount_history_api),
    path('promotions/discount/active', promotions.get_active_user_discount_api),
    path('promotions/discount/webengage/private_create', CreateUserDiscountApi.as_view()),
    path('promotions/discount/webengage/private_check_user_discount', CheckActiveUserDiscountApi.as_view()),

    # Gift
    path('gift/packages', gift.gift_packages_list),
    path('gift/create-gift', gift.create_gift_card),
    path('gift/redeem', gift.redeem_logged_in_user_gift_card),
    path('gift/redeem-lightning', gift.public_redeem_lightning_gift_card),
    path('gift/user-gifts', gift.user_gift_cards_list),
    path('gift/create-gift-batch', gift.create_gift_batch_request),
    path('gift/confirm-gift-batch', gift.confirm_gift_batch),
    path('gift/resend-gift-otp', gift.resend_gift_otp),
    path('gift/<str:code>', gift.redeem_landing),
    path('gift/padro/provinces', get_padro_provinces),
    path('gift/padro/provinces/<int:province_code>', get_padro_province_cities),

    # Redeem
    path('redeem/pgala2022/info', redeem.get_redeem_info),
    path('redeem/pgala2022/request', redeem.request_redeem),
    path('redeem/pgala2022/unblock', redeem.request_unblock),

    # Smart Support
    path('support/nxbo/register', support.nxbo_register),
    path('support/kyc/refresh-mobile-identity', support.kyc_refresh_mobile_identity),
    path('support/kyc/refresh-level1', support.kyc_refresh_level1),
    path('support/wallets/refresh-deposit', support.wallets_refresh_deposit),

    # Authentication
    path('auth/login/', auth_views.LoginView.as_view(), name='rest_login'),
    path('auth/logout/', auth_views.LogoutView.as_view(), name='rest_logout'),
    path('auth/google/', auth_views.google_social_login, name='google_login'),
    path('auth/user/', auth_views.UserDetailsView.as_view(), name='rest_user_details'),
    path('auth/user/change-password', auth_views.change_password),
    path('auth/user/social-login-set-password', auth_views.set_password_for_social_users),
    path('auth/registration/', auth_views.RegisterView.as_view(), name='rest_register'),
    path('auth/registration/verify-email/', auth_views.VerifyEmailView.as_view(), name='rest_verify_email'),
    path('auth/forget-password/', auth_views.forget_password, name='forget_password'),
    path('auth/forget-password-commit/', auth_views.forget_password_commit, name='forget_password_commit'),
    path('auth/ws/token/', auth_views.WebsocketAuth.as_view()),
    path('users/login-attempts', auth_views.users_login_attempts),
    path('users/email-activation-redirect', auth_views.email_activation_redirect),
    path('users/request-tfa-removal', auth_views.RemoveTFARequest.as_view()),
    path('users/confirm-tfa-removal/<username>', auth_views.RemoveTFAConfirm.as_view()),

    # Android App
    path('app/request-link', android_views.request_link),

    # Direct Calls
    path('direct/confirm-withdraw/<int:withdraw>/<slug:token>', wallet.wallets_withdraw_direct_confirm),

    # Admin
    path('bitex/admin/', admin.site.urls),
    re_path(r'^media/(?P<path>.*)$', base_views.serve_media),

    # Admin Reports
    path('bitex/wallets/', report.wallets_overview),
    path('bitex/wallets/update-balance', report.wallets_update_balance),
    path('bitex/status/', status_report.overview),
    path('bitex/control-panel/', report.control_panel),

    # Metrics
    path('bitex/metrics', report.nobitex_metrics),
    path('bitex/prometheus', metrics.metrics),

    # Blockchain Special APIs
    path('blockchain/get-balance', blockchain.get_balance),

    # Admin wallet APIs
    path('bitex/wallets/create-wallet-bip39', staff_member_required(wallet.CreateWalletBIP39View.as_view())),
    path('bitex/wallets/create-wallet', staff_member_required(wallet.CreateWalletView.as_view())),
    path('bitex/wallets/import-cold-wallet', staff_member_required(wallet.CreateWalletFromColdView.as_view())),
    path('bitex/wallets/tron/freeze', staff_member_required(wallet.FreezeTronWalletView.as_view())),
    path('bitex/wallets/tron/unfreeze', staff_member_required(wallet.UnfreezeTronWalletView.as_view())),
    path('bitex/wallets/tron/mint', staff_member_required(wallet.MintTronZWalletView.as_view())),
    path('bitex/wallets/tron/zbalance', staff_member_required(wallet.BalanceTronZWalletView.as_view())),
    path('bitex/wallets/contract-extract', staff_member_required(wallet.ExtractContractAddressesView.as_view())),

    # Basic Resources
    path('robots.txt', TemplateView.as_view(template_name='robots.txt'), name='robots'),
    re_path(
        r'^(favicon\.ico|apple-touch-icon\.png|apple-touch-icon-precomposed\.png)',
        cache_control(max_age=60*60*24)(RedirectView.as_view(url=settings.STATIC_URL + 'nobitex.png'))
    ),

    # Captcha
    path('captcha/select', captcha_views.captcha_select_view),
    path('captcha/get-captcha-key', captcha_views.get_captcha_key),
    re_path(r'captcha/image/(?P<key>\w+)/$', captcha_image_views, kwargs={'scale': 2}),
    re_path(r'captcha/image//image/(?P<key>\w+)/$', captcha_image_views, kwargs={'scale': 2}),
    re_path(r'captcha/image/image/(?P<key>\w+)/$', captcha_image_views, kwargs={'scale': 2}),
    re_path(r'image/(?P<key>\w+)/$', captcha_image_views, name='captcha-image', kwargs={'scale': 2}),

    # CoinMarketCap
    path('coinmarketcap/v1/summary', coinmarketcap.MarketSummaryView.as_view()),
    path('coinmarketcap/v1/assets', coinmarketcap.MarketAssetsView.as_view()),
    path('coinmarketcap/v1/ids', coinmarketcap.MarketIdsView.as_view()),
    path('coinmarketcap/v1/ticker', coinmarketcap.MarketTickerView.as_view()),
    path('coinmarketcap/v1/orderbook/<str:market_pair>', coinmarketcap.OrderBookView.as_view()),
    path('coinmarketcap/v1/trades/<str:market_pair>', coinmarketcap.TradesView.as_view()),

    # Ticketing
    path('ticketing/topics', ticketing.get_topics),
    path('ticketing/tickets', ticketing.get_list_of_user_tickets),
    path('ticketing/tickets/<int:pk>', ticketing.get_details_of_ticket),
    path('ticketing/tickets/create', ticketing.post_ticket),
    path('ticketing/comments/create', ticketing.post_comment),
    path('ticketing/tickets/<int:pk>/close', ticketing.close_ticket),
    path('ticketing/tickets/<int:pk>/rate', ticketing.rate_ticket),
    path('ticketing/attachments/<str:file_hash>', ticketing.download_ticket_attachment, name='download_ticket_attachment'),

    # Pool
    path('liquidity-pools/list', pool.LiquidityPoolsListView.as_view()),
    path('liquidity-pools/<int:id>/delegations', pool.LiquidityPoolDelegateView.as_view()),
    path(
        "liquidity-pools/delegations/<int:pk>/revoke",
        pool.DelegationRevokeRequestCreateView.as_view(),
    ),
    path("liquidity-pools/delegation-revoke-requests/list", pool.DelegationRevokeRequestListView.as_view()),
    path('liquidity-pools/delegations/list', pool.LiquidityPoolListDelegationsView.as_view()),
    path('liquidity-pools/delegation-transactions/list', pool.LiquidityPoolListDelegationTxsView.as_view()),
    path(
        "liquidity-pools/<int:pk>/unfilled-capacity-alert/create",
        pool.PoolUnfilledCapacityAlertCreateView.as_view(),
    ),
    path(
        "liquidity-pools/<int:pk>/unfilled-capacity-alert/delete",
        pool.PoolUnfilledCapacityAlertDeleteView.as_view(),
    ),
    path('liquidity-pools/delegation-profits/list', pool.UserDelegationProfitsListView.as_view()),
    path('liquidity-pools/delegations/<int:pk>/current-calender', pool.UserDelegationCalenderView.as_view()),

    # Integrations
    path('integrations/webengage/private_ssp', SSPMessageApi.as_view()),
    path('integrations/webengage/private_esp', ESPMessageApi.as_view()),
    path('webhooks/webengage/esp_delivery_status_webhook/<str:bulk_id>', ESPDeliveryStatusApi.as_view()),

    # Staking (Earn)
    path('earn/plan', staking.plans_view),
    path('earn/plan/offers', staking.plan_offers_view),
    path('earn/plan/watch', staking.watch_plan_view),
    path('earn/plan/watch/add', staking.add_plan_watch_view),
    path('earn/plan/watch/remove', staking.remove_plan_watch_view),
    path('earn/request', staking.requests_list_view),
    path('earn/request/create', staking.create_request_view),
    path('earn/request/end', staking.end_request_view),
    path('earn/request/instant-end', staking.instant_end_request_view),
    path('earn/subscription', staking.user_subscription_view),
    path('earn/unsubscription', staking.user_unsubscription_view),
    path('earn/plan/auto-extend/enable', staking.enable_auto_extend_view),
    path('earn/plan/auto-extend/disable', staking.disable_auto_extend_view),
    path('earn/plan/best-performing', staking.best_performing_plans_view),

    # Recovery
    path('recovery/currencies/list', recovery.RecoveryCurrencyListView.as_view()),
    path('recovery/networks/list', recovery.RecoveryNetworkListView.as_view()),
    path('recovery/recovery-requests', recovery.RecoveryRequestView.as_view()),
    path('recovery/recovery-requests/check-hash', recovery.CheckRecoveryRequestView.as_view()),
    path('recovery/recovery-requests/<int:id>/reject', recovery.RejectRecoveryRequestView.as_view()),
    path('recovery/all-deposit-address', recovery.GetAllAvailableDepositAddresses.as_view()),
    path('recovery/recovery-requests/<int:id>/reject-reasons', recovery.GetRejectReasonsView.as_view()),

    # Earn
    path('earn/balances', earn.EarnBalances.as_view()),

    # Vip Credit
    path('credit/lend', credit.lend_view),
    path('credit/repay', credit.repay_view),
    path('credit/debt-detail', credit.user_debt_detail_view),
    path('credit/plan', credit.user_credit_plan_view),
    path('credit/transactions', credit.user_history_view),
    path('credit/lend-calculator', credit.lending_calculator_view),
    path('credit/withdraw-calculator', credit.withdraw_calculator_view),
    # API Key
    path('apikeys/create', apikey.create_key_request),
    path('apikeys/list', apikey.list_keys_request),
    path('apikeys/delete/<str:public_key>', apikey.delete_key_request),
    path('apikeys/update/<str:public_key>', apikey.update_key_request),
    # System
    path('system/bot-transactions', ListBotTransactionView.as_view(), name='bot_transactions_list_get'),

    # Social Trading
    path('social-trade/options', social_trade.OptionsView.as_view()),
    path('social-trade/avatars', social_trade.SocialTradeAvatarListView.as_view()),
    path('social-trade/leadership-requests', social_trade.LeadershipRequestView.as_view(), name='leadership_request_list_create'),
    path('social-trade/subscriptions', social_trade.SubscriptionView.as_view()),
    path('social-trade/leaders/positions', social_trade.LeadersPositionsView.as_view()),
    path('social-trade/leaders/<int:leader_id>/orders', social_trade.LeaderOrdersView.as_view()),
    path(
        'social-trade/subscriptions/<int:subscription_id>/unsubscribe',
        social_trade.UnsubscribeView.as_view(),
        name='unsubscribe',
    ),
    path('social-trade/leaders', social_trade.LeaderboardView.as_view(), name='leader-board'),
    path('social-trade/user-dashboard', social_trade.UserDashboardView.as_view(), name='user-dashboard'),
    path(
        'social-trade/subscriptions/<int:subscription_id>/change-auto-renewal',
        social_trade.ChangeAutoRenewalView.as_view(),
        name='change-auto-renewal',
    ),
    path(
        'social-trade/subscriptions/<int:subscription_id>/change-notif-enabled',
        social_trade.ChangeSendNotifView.as_view(),
    ),
    path(
        'social-trade/leaders/<int:leader_id>/profile', social_trade.LeaderProfileView.as_view(), name='leader-profile'
    ),
    # OAuth
    path('oauth/client/<str:client_id>', oauth.ApplicationView.as_view(), name='application_info'),
    path('oauth/authorization', oauth.AuthorizationAPIView.as_view()),
    path('oauth/token', oauth.TokenView.as_view()),
    path('oauth/granted-accesses', oauth.GrantedAccessesView.as_view(), name='granted-accesses-list'),
    # OAuth services
    path('oauth-services/user-info', oauth_services.UserInfoView.as_view(), name='oauth-user-info'),
    path('oauth-services/profile-info', oauth_services.ProfileInfoView.as_view(), name='oauth-profile-info'),
    path('oauth-services/identity-info', oauth_services.IdentityInfoView.as_view(), name='oauth-national-code'),
    # Asset Backed Credit
    path(
        'asset-backed-credit/services/<int:service_id>/permission/request',
        abc_views.UserServicePermissionRequestView.as_view(),
    ),
    path('asset-backed-credit/services/<int:service_id>/activate', abc_views.VerifyOTPView.as_view()),
    path('asset-backed-credit/services/<int:service_id>/deactivate', abc_views.ServiceDeactivateView.as_view()),
    path('asset-backed-credit/user-service-permissions/list', abc_views.UserServicePermissionListView.as_view()),
    path('asset-backed-credit/options', abc_views.OptionsView.as_view()),
    path('asset-backed-credit/financial-summary', abc_views.FinancialSummaryView.as_view()),
    path('asset-backed-credit/user-services/list', abc_views.UserServiceListView.as_view()),
    path('asset-backed-credit/user-services/create', abc_views.CreateUserServiceView.as_view()),
    path('asset-backed-credit/user-services/<int:user_service_id>/close', abc_views.CloseUserServiceView.as_view()),
    path(
        'asset-backed-credit/user-services/<int:user_service_id>/total-installments',
        abc_views.TotalInstallmentsInquiryView.as_view(),
    ),
    path(
        'asset-backed-credit/user-services/<int:user_service_id>/debt/edit',
        abc_views.UserServiceDebtEditView.as_view(),
    ),
    path('asset-backed-credit/user-services/<int:user_service_id>/debt', abc_views.UserServiceDebtView.as_view()),
    path('asset-backed-credit/withdraws/create', abc_views.WalletWithdrawView.as_view()),

    path(
        'asset-backed-credit/debit/cards',
        abc_views.DebitCardListCreateView.as_view(),
        name='abc-debit-card-list-create',
    ),
    path(
        'asset-backed-credit/debit/cards/otp/request',
        abc_views.DebitCardOTPRequestView.as_view(),
        name='abc-debit-card-otp-request',
    ),
    path(
        'asset-backed-credit/debit/cards/otp/verify',
        abc_views.DebitCardOTPVerifyView.as_view(),
        name='abc-debit-card-otp-verify',
    ),
    path(
        'asset-backed-credit/debit/cards/<int:card_id>/suspend',
        abc_views.DebitCardSuspendView.as_view(),
        name='abc-debit-card-suspend',
    ),
    path(
        'asset-backed-credit/debit/cards/<int:card_id>/transfers',
        abc_views.DebitCardTransferTransactionListView.as_view(),
        name='abc-debit-card-transfer-transactions',
    ),
    path(
        'asset-backed-credit/debit/cards/<int:card_id>/settlements',
        abc_views.DebitCardSettlementTransactionListView.as_view(),
        name='abc-debit-card-settlement-transactions',
    ),
    path(
        'asset-backed-credit/wallets/debit', abc_views.DebitWalletListAPIView.as_view(), name='abc-debit-wallets-list'
    ),
    path(
        'asset-backed-credit/wallets/collateral',
        abc_views.CollateralWalletListAPIView.as_view(),
        name='abc-collateral-wallets-list',
    ),
    # Asset Backed Credit - third party urls
    path('asset-backed-credit/v1/estimate', abc_views.EstimationView.as_view(), name='abc_estimate_url'),
    path('asset-backed-credit/v1/lock', abc_views.LockView.as_view(), name='abc_lock_url'),
    path('asset-backed-credit/v1/unlock', abc_views.UnlockView.as_view(), name='abc_unlock_url'),
    path('asset-backed-credit/v1/settlement', abc_views.SettlementView.as_view(), name='abc_settlement_url'),
    path(
        'asset-backed-credit/v1/debit/transaction',
        abc_views.TransactionView.as_view(),
        name='abc_debit_transaction_url',
    ),
    path(
        'asset-backed-credit/debit/cards/<int:card_id>/activate',
        abc_views.DebitCardActivateView.as_view(),
        name='abc_debit_card_activate_url',
    ),
    path(
        'asset-backed-credit/debit/cards/<int:card_id>/disable',
        abc_views.DebitCardDisableView.as_view(),
        name='abc_debit_card_disable_url',
    ),
    path(
        'asset-backed-credit/debit/cards/<int:card_id>/overview',
        abc_views.DebitCardOverviewView.as_view(),
        name='abc-debit-card-overview',
    ),
    path(
        'asset-backed-credit/v1/services/<int:service_id>/calculator',
        abc_views.LoanCalculatorView.as_view(),
        name='abc_loan_calculator_url',
    ),
    path('asset-backed-credit/wallets/deposit', abc_views.WalletDepositView.as_view(), name='abc_wallet_deposit_url'),
    # Direct Debit
    path('direct-debit/banks', direct_debit.DirectDebitBankView.as_view({'get': 'get'}), name='direct_debit_banks'),
    path('direct-debit/contracts', direct_debit.DirectDebitContractView.as_view({'get': 'get'})),
    path('direct-debit/contracts/create', direct_debit.DirectDebitCreateContractView.as_view({'post': 'post'})),
    path(
        'direct-debit/contracts/<int:pk>',
        direct_debit.DirectDebitEditContractView.as_view({'post': 'change_status', 'put': 'update_contract'}),
    ),
    path('direct-debit/deposit', direct_debit.DirectDebitDepositView.as_view({'post': 'post'})),
    path(
        'direct-debit/contracts/<str:trace_id>/callback',
        direct_debit.ContractCallbackView.as_view(),
        name='create_contract_callback',
    ),
    path(
        'direct-debit/contracts/<str:trace_id>/update-callback',
        direct_debit.UpdateContractCallbackView.as_view(),
        name='update_contract_callback',
    ),

    # Websocket
    path('ws/healthcheck/publish', healthcheck_ws_publish),
    path('ws/status', ws_status),
    # Corporate Banking
    path('cobank/deposit-info', corporate_banking.CoBankDepositInfoAPI.as_view()),
    path('cobank/card-deposit-info', corporate_banking.CoBankCardDepositInfoAPI.as_view()),
]


# Django Debug Toolbar
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns


if not settings.IS_PROD:
    from exchange.liquidator import views as liquidator

    urlpatterns += [
        # test
        path('QA/liquidation-requests', liquidator.LiquidationRequestCreateView.as_view()),
        path('QA/wallets/charge', wallet.create_bulk_transactions),
    ]


# Internal Apis
if settings.IS_TEST_RUNNER or settings.IS_INTERNAL_INSTANCE:
    urlpatterns += [
        # Account
        path('internal/get-user', internal_accounts.get_user_view),
        path('internal/users/<uuid:user_id>/profile', internal_accounts.internal_user_profile),
        path('internal/users/<uuid:user_id>/send-otp', internal_accounts.internal_send_otp),
        path('internal/users/<uuid:user_id>/verify-otp', internal_accounts.internal_verify_otp),
        path('internal/users/<uuid:user_id>/verify-totp', internal_accounts.internal_verify_totp),
        path('internal/users/<uuid:user_id>/add-restriction', internal_accounts.internal_add_restriction),
        path('internal/users/<uuid:user_id>/remove-restriction', internal_accounts.internal_remove_restriction),

        # ABC
        path('internal/asset-backed-credit/debit/cards/enable', abc_views.internal_enable_debit_card_batch),
        path(
            'internal/asset-backed-credit/user-financial-limits',
            abc_views.UserFinancialServiceLimitList.as_view(),
            name='user_financial_limit_list',
        ),
        path(
            'internal/asset-backed-credit/user-financial-limits/<int:pk>',
            abc_views.UserFinancialServiceLimitDetail.as_view(),
            name='user_financial_limit_detail',
        ),
        path(
            'internal/asset-backed-credit/user-services/<int:user_service_id>/close',
            abc_views.UserServiceForceCloseView.as_view(),
            name='user_service_force_close_view',
        ),
        path(
            'internal/asset-backed-credit/wallets/debit/balances',
            abc_views.DebitWalletsBalanceListInternalAPI.as_view(),
            name='abc-debit-wallets-balances-list',
        ),
        # Wallet
        path('internal/wallets/bulk-transfer', internal_bulk_transfer_view),
        path('internal/wallets/withdraw-rial', internal_withdraw_rial_view),
        path('internal/wallets/list', internal_list_wallets_view),
        path('internal/transactions/batch-create', internal_batch_transaction_view),
    ]
