import asyncio
import datetime
import logging
import readline  # imported to allow pasting long lines into `input` function
import time
from typing import Dict, Any
import uuid

import enablebanking

logging.getLogger().setLevel(logging.INFO)

REDIRECT_URL = "https://enablebanking.com/auth_redirect"  # PUT YOUR REDIRECT URI HERE


CONNECTOR_NAME = "Nordea"
CONNECTOR_COUNTRY = "FI"
CONNECTOR_SETTINGS = {
    "sandbox": True,
    "consentId": None,
    "accessToken": None,
    "refreshToken": None,
    "redirectUri": REDIRECT_URL,
    "country": "DK",
    "language": None,
    "clientId": "<YOUR CLIENT ID>",
    "clientSecret": "<YOUR CLIENT SECRET>",
    "signKeyPath": "/path/to/your/private.key",
}


def read_redirected_url(url, redirect_url):
    print("Please, open this page in browser: " + url)
    print("Login, authenticate and copy paste back the URL where you got redirected.")
    print(f"URL: (starts with %s): " % redirect_url)

    redirected_url = input()  # insert your url
    return redirected_url


async def get_connector_meta(
    connector_name: str, connector_country: str
) -> enablebanking.MetaApi:
    meta_api = enablebanking.MetaApi(enablebanking.ApiClient())
    for conn in (await meta_api.get_connectors(country=connector_country)).connectors:
        if conn.name == connector_name:
            return conn
    raise Exception("Meta not found")


async def main():
    api_meta = await get_connector_meta(
        CONNECTOR_NAME, CONNECTOR_COUNTRY
    )  # get meta information for current connector

    api_client = enablebanking.ApiClient(
        CONNECTOR_NAME, connector_settings=CONNECTOR_SETTINGS
    )  # Create client instance.

    auth_api = enablebanking.AuthApi(api_client)  # Create authentication interface.

    client_info = enablebanking.ClientInfo()
    connector_psu_headers = api_meta.required_psu_headers
    if "psuIpAddress" in connector_psu_headers:
        client_info.psu_ip_address = "10.10.10.10"

    if "psuUserAgent" in connector_psu_headers:
        client_info.psu_user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/12.1.1 Safari/605.1.15"

    await auth_api.set_client_info(client_info=client_info)

    access = enablebanking.Access(
        valid_until=(datetime.datetime.now() + datetime.timedelta(days=89))
    )
    get_auth_params: Dict[str, Any] = {"state": str(uuid.uuid4())}
    if api_meta.auth_info[0].info.access:
        get_auth_params["access"] = access
    auth_response = await auth_api.get_auth(**get_auth_params)

    make_token_response = None
    if auth_response.url:
        # if url is returned, then we are doing redirect flow
        redirected_url = read_redirected_url(auth_response.url, REDIRECT_URL)
        query_params = await auth_api.parse_redirect_url(redirected_url)
        logging.info("Parsed query: %s", query_params)
        make_token_response = await auth_api.make_token(
            "authorization_code",  # grant type, MUST be set to "authorization_code"
            code=query_params.code,
            auth_env=auth_response.env,
        )
    else:
        # decoupled flow otherwise
        # Doing a retry to check periodically whether user has already authorized a consent
        sleep_time = 3
        for _ in range(3):
            try:
                make_token_response = await auth_api.make_token(
                    "authorization_code",  # grant type, MUST be set to "authorization_code"
                    code="",
                    auth_env=auth_response.env,
                )
            except enablebanking.MakeTokenException as e:
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
        consent = await aisp_api.modify_consents(access=access)
        logging.debug(f"Consent: {consent}")
        try:
            # If returned consent has a redirect url, we need to redirect a PSU there
            consent_url = consent.links.redirect.href
            redirect_url = read_redirected_url(consent_url, REDIRECT_URL)
            logging.debug(f"Redirect url: {redirect_url}")
        except AttributeError:
            pass

    accounts = await aisp_api.get_accounts()
    logging.info("Accounts info: %s", accounts)

    if api_meta.modify_consents_info[0].info.accounts_required:
        # bank requires to create a consent with account ids specified
        account_ids = [
            enablebanking.AccountIdentification(iban=acc.account_id.iban)
            for acc in accounts.accounts
        ]
        access.accounts = account_ids
        consent = await aisp_api.modify_consents(access=access)
        logging.debug(f"Consent: {consent}")
        try:
            # If returned consent has a redirect url, we need to redirect a PSU there
            consent_url = consent.links.redirect.href
            redirect_url = read_redirected_url(consent_url, REDIRECT_URL)
            logging.debug(f"Redirect url: {redirect_url}")
        except AttributeError:
            pass

    for account in accounts.accounts:
        transactions = await aisp_api.get_account_transactions(account.resource_id)
        logging.info("Transactions info: %s", transactions)

        balances = await aisp_api.get_account_balances(account.resource_id)
        logging.info("Balances info: %s", balances)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
