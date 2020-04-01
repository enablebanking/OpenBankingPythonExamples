import logging

import enablebanking

import util

logging.getLogger().setLevel(logging.INFO)

REDIRECT_URL = "https://enablebanking.com"  # PUT YOUR REDIRECT URI HERE


def alior_settings():
    return {
        "sandbox": True,
        "clientId": "client-id",  # API client ID
        "clientSecret": "client-secret",
        "certPath": "cert-path",  # Path or URI QWAC certificate in PEM format
        "keyPath": "key-path",  # Path or URI to QWAC certificate private key in PEM format
        "signKeyPath": "sign-key-path",  # Path or URI to QSeal certificate in PEM format
        "signPubKeySerial": "sign-pub-key-serial",  # Public serial key of the QSeal certificate located in signKeyPath
        "signFingerprint": "sign-fingerprint",
        "signCertUrl": "sign-cert-url",
        "accessToken": None,
        "consentId": None,
        "redirectUri": REDIRECT_URL,
        "paymentAuthRedirectUri": REDIRECT_URL,  # URI where clients are redirected to after payment authorization.
        "paymentAuthState": "test"  # This value returned to paymentAuthRedirectUri after payment authorization.
    }


def main():
    api_client = enablebanking.ApiClient("Alior", connector_settings=alior_settings())  # Create client instance.
    pisp_api = enablebanking.PISPApi(api_client)

    payment_request_resource = enablebanking.PaymentRequestResource(
        payment_type_information=enablebanking.PaymentTypeInformation(service_level="SEPA",  # will be resolved to "pis:EEA"
                                                                      local_instrument="SEPA"),  # set explicitly, can also be for example SWIFT or ELIXIR
        credit_transfer_transaction=[
            enablebanking.CreditTransferTransaction(
                instructed_amount=enablebanking.AmountType(
                    amount="12.25",
                    currency="EUR"),
                beneficiary=enablebanking.Beneficiary(
                    creditor=enablebanking.PartyIdentification(name="Creditor Name",
                                                               postal_address={"country": "RO",
                                                                               "addressLine": ["Creditor Name",
                                                                                               "Creditor Address 1",
                                                                                               "Creditor Address 2"]}),
                    creditor_account=enablebanking.AccountIdentification(iban="RO56ALBP0RON421000045875"),
                ),
                remittance_information=["Some remittance information"],
            ),
        ],
        debtor=enablebanking.PartyIdentification(name="Debtor Name",
                                                 postal_address={"country": "PL",
                                                                 "addressLine": ["Debtor Name",
                                                                                 "Debtor Address 1",
                                                                                 "Debtor Address 2"]}),
        debtor_account=enablebanking.AccountIdentification(iban="PL63249000050000400030900682"),
    )
    request_creation = pisp_api.make_payment_request(payment_request_resource)
    logging.info("Request creation: %s", request_creation)

    redirected_url = util.read_redirected_url(request_creation.links.consent_approval.href, REDIRECT_URL)  # calling helper functions for CLI interaction
    parsed_query_params = util.parse_redirected_url(redirected_url)
    logging.info("Query params: %s", parsed_query_params)

    payment_request_confirmation = pisp_api.make_payment_request_confirmation(
        request_creation.payment_request_resource_id,
        confirmation=enablebanking.PaymentRequestConfirmation(
            psu_authentication_factor=parsed_query_params.get("code"),
            payment_request=payment_request_resource
        ))
    logging.info("Payment request confirmation: %s", payment_request_confirmation)


if __name__ == "__main__":
    main()
