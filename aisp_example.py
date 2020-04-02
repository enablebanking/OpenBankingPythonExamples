import logging

import enablebanking

logging.getLogger().setLevel(logging.INFO)

REDIRECT_URL = "https://enablebanking.com"  # PUT YOUR REDIRECT URI HERE


def nordea_settings():
    return {
        "clientId": "client-id",  # API client ID
        "clientSecret": "client-secret",
        "certPath": "cert-path",  # Path or URI to QWAC certificate in PEM format
        "keyPath": "key-path",  # Path or URI to QWAC certificate private key in PEM format
        "country": "FI",
        "sandbox": True,
        "consentId": None,
        "accessToken": None,
        "redirectUri": REDIRECT_URL,
        "language": "fi"
    }

def read_redirected_url(url, redirect_url):
    print("Please, open this page in browser: " + url)
    print("Login, authenticate and copy paste back the URL where you got redirected.")
    print(f"URL: (starts with %s): " % redirect_url)

    redirected_url = input()  # insert your url
    return redirected_url


def main():
    api_client = enablebanking.ApiClient("Nordea", connector_settings=nordea_settings())  # Create client instance.

    auth_api = enablebanking.AuthApi(api_client)  # Create authentication interface.

    auth_url = auth_api.get_auth(state="test").url  # state to pass to redirect URL

    redirected_url = read_redirected_url(auth_url, REDIRECT_URL)
    query_params = auth_api.parse_redirect_url(redirected_url)
    logging.info("Parsed query: %s", query_params)

    token = auth_api.make_token(grant_type="authorization_code",  # grant type, MUST be set to "authorization_code"
                                code=query_params.code)
    logging.info("Token: %s", token)

    aisp_api = enablebanking.AISPApi(api_client)  # api_client has already accessToken and refreshToken applied after call to makeToken()

    accounts = aisp_api.get_accounts()
    logging.info("Accounts info: %s", accounts)

    for account in accounts.accounts:
        transactions = aisp_api.get_account_transactions(account.resource_id)
        logging.info("Transactions info: %s", transactions)

        balances = aisp_api.get_account_balances(account.resource_id)
        logging.info("Balances info: %s", balances)


if __name__ == "__main__":
    main()
