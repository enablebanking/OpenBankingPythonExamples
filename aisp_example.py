import logging
import readline  # imported to allow pasting long lines into `input` function
import time
from typing import Dict, Any
import uuid

import enablebanking

logging.getLogger().setLevel(logging.INFO)

REDIRECT_URL = "https://enablebanking.com"  # PUT YOUR REDIRECT URI HERE


CONNECTOR_NAME = "Nordea"
CONNECTOR_COUNTRY = "SE"
NORDEA_SETTINGS = {
    "sandbox": True,
    "consentId": None,
    "accessToken": None,
    "redirectUri": REDIRECT_URL,  # your redirect uri
    "country": CONNECTOR_COUNTRY,
    "business": None,
    "clientId": "client_id_here",  # API Client ID
    "clientSecret": "client_secret_here",  # API Client Secret
    "signKeyPath": "/path/to/private/key.key",  # Path or URI to QSeal private key in PEM format
    "language": None,
    "paymentAuthRedirectUri": "https://enablebanking.com/auth_redirect",
    "paymentAuthState": "test",
}


def read_redirected_url(url, redirect_url):
    print("Please, open this page in browser: " + url)
    print("Login, authenticate and copy paste back the URL where you got redirected.")
    print(f"URL: (starts with %s): " % redirect_url)

    redirected_url = input()  # insert your url
    return redirected_url


def get_connector_meta(
    connector_name: str, connector_country: str
) -> enablebanking.MetaApi:
    meta_api = enablebanking.MetaApi(enablebanking.ApiClient())
    for conn in meta_api.get_connectors(country=connector_country).connectors:
        if conn.name == connector_name:
            return conn
    raise Exception("Meta not found")


def main():
    api_meta = get_connector_meta(
        CONNECTOR_NAME, CONNECTOR_COUNTRY
    )  # get meta information for current connector

    api_client = enablebanking.ApiClient(
        "Nordea", connector_settings=NORDEA_SETTINGS
    )  # Create client instance.

    auth_api = enablebanking.AuthApi(api_client)  # Create authentication interface.

    get_auth_params: Dict[str, Any] = {"state": str(uuid.uuid4())}
    if api_meta.auth_info[0].info.access:
        # you can pass additional parameters to Access model and customie requested consent from a PSU
        get_auth_params["access"] = enablebanking.Access()
    if api_meta.auth_info[0].info.user_id_required:
        get_auth_params["user_id"] = "some_id"
    if api_meta.auth_info[0].info.password_required:
        get_auth_params["password"] = "some_password"
    auth_response = auth_api.get_auth(**get_auth_params)

    make_token_response = None
    if auth_response.url:
        # if url is returned, then we are doing redirect flow
        redirected_url = read_redirected_url(auth_response.url, REDIRECT_URL)
        query_params = auth_api.parse_redirect_url(redirected_url)
        logging.info("Parsed query: %s", query_params)
        make_token_response = auth_api.make_token(
            "authorization_code",  # grant type, MUST be set to "authorization_code"
            query_params.code,
            auth_env=auth_response.env,
        )
    else:
        # decoupled flow otherwise
        # Doing a retry to check periodically whether user has already authorized a consent
        sleep_time = 3
        for _ in range(3):
            try:
                make_token_response = auth_api.make_token(
                    "authorization_code",  # grant type, MUST be set to "authorization_code"
                    code="",
                    auth_env=auth_response.env,
                )
            except enablebanking.UnauthorizedException:
                logging.debug(
                    f"Failed to get authorization code, sleeping for {sleep_time} seconds"
                )
                time.sleep(sleep_time)
            else:
                break

    logging.info("Token: %s", make_token_response)

    aisp_api = enablebanking.AISPApi(
        api_client
    )  # api_client has already accessToken and refreshToken applied after call to makeToken()

    if api_meta.modify_consents_info[0].info.before_accounts:
        # bank requires to create a consent explicitly before accessing list of accounts
        access = enablebanking.Access()
        consent = aisp_api.modify_consents(access=access)
        logging.debug(f"Consent: {consent}")
        try:
            # If returned consent has a redirect url, we need to redirect a PSU there
            consent_url = consent.links.redirect.href
            redirect_url = read_redirected_url(consent_url, REDIRECT_URL)
            logging.debug(f"Redirect url: {redirect_url}")
        except AttributeError:
            pass

    accounts = aisp_api.get_accounts()
    logging.info("Accounts info: %s", accounts)

    if api_meta.modify_consents_info[0].info.accounts_required:
        # bank requires to create a consent with account ids specified
        account_ids = [
            enablebanking.AccountIdentification(iban=acc.account_id.iban)
            for acc in accounts.accounts
        ]
        access = enablebanking.Access(accounts=account_ids)
        consent = aisp_api.modify_consents(access=access)
        logging.debug(f"Consent: {consent}")
        try:
            # If returned consent has a redirect url, we need to redirect a PSU there
            consent_url = consent.links.redirect.href
            redirect_url = read_redirected_url(consent_url, REDIRECT_URL)
            logging.debug(f"Redirect url: {redirect_url}")
        except AttributeError:
            pass

    for account in accounts.accounts:
        transactions = aisp_api.get_account_transactions(account.resource_id)
        logging.info("Transactions info: %s", transactions)

        balances = aisp_api.get_account_balances(account.resource_id)
        logging.info("Balances info: %s", balances)


if __name__ == "__main__":
    main()
