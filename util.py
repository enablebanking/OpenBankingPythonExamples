from urllib.parse  import urlparse, parse_qs


def parse_redirected_url(redirected_url):
    """Parse query string into dict"""
    return {x: y[0] for x, y in parse_qs(urlparse(redirected_url).query).items()}


def read_redirected_url(url, redirect_url):
    print("Please, open this page in browser: " + url)
    print("Login, authenticate and copy paste back the URL where you got redirected.")
    print(f"URL: (starts with %s): " % redirect_url)

    redirected_url = input()  # insert your url
    return redirected_url

