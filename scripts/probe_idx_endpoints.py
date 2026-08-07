import json

import httpx

# Official IDX website backend used by the
# current Company Profiles page.
# This is a website endpoint and may change
# without API-version guarantees.

COMPANY_PAGE = (
    "https://www.idx.id/en/"
    "listed-companies/company-profiles/"
)

ENDPOINTS = (
    (
        "IDX current-domain candidate",
        (
            "https://www.idx.id/"
            "primary/ListedCompany/"
            "GetCompanyProfiles"
        ),
    ),
    (
        "IDX legacy-domain endpoint",
        (
            "https://www.idx.co.id/"
            "primary/ListedCompany/"
            "GetCompanyProfiles"
        ),
    ),
)


def inspect_json(payload: object) -> None:
    print(
        "JSON type          : "
        f"{type(payload).__name__}"
    )

    if isinstance(payload, list):
        print(
            "List rows          : "
            f"{len(payload)}"
        )

        if payload:
            first = payload[0]

            if isinstance(first, dict):
                print(
                    "First row keys     : "
                    f"{list(first.keys())[:20]}"
                )

        return

    if not isinstance(payload, dict):
        return

    print(
        "Top-level keys     : "
        f"{list(payload.keys())[:30]}"
    )

    for key in (
        "data",
        "Data",
        "results",
        "Results",
    ):
        value = payload.get(key)

        if isinstance(value, list):
            print(
                f"{key} rows"
                f"{' ' * max(1, 14 - len(key))}: "
                f"{len(value)}"
            )

            if value and isinstance(
                value[0],
                dict,
            ):
                print(
                    "First row keys     : "
                    f"{list(value[0].keys())[:20]}"
                )


def main() -> None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/151.0 Safari/537.36"
        ),
        "Accept": (
            "application/json, "
            "text/plain, */*"
        ),
        "Accept-Language": (
            "en-US,en;q=0.9,id;q=0.8"
        ),
        "Referer": COMPANY_PAGE,
    }

    params = {
        "emitenType": "s",
        "start": 0,
        "length": 9999,
    }

    with httpx.Client(
        headers=headers,
        timeout=30.0,
        follow_redirects=True,
    ) as client:
        print(
            "IDX endpoint diagnostic"
        )
        print(
            "======================="
        )

        print()
        print(
            "Priming official page..."
        )

        try:
            page_response = client.get(
                COMPANY_PAGE
            )

            print(
                "Company page status : "
                f"{page_response.status_code}"
            )
            print(
                "Company page URL    : "
                f"{page_response.url}"
            )
            print(
                "Company page type   : "
                f"{page_response.headers.get('content-type')}"
            )
            print(
                "Cookies received    : "
                f"{len(client.cookies)}"
            )

        except httpx.HTTPError as exc:
            print(
                "Company page error  : "
                f"{exc}"
            )

        for name, endpoint in ENDPOINTS:
            print()
            print(
                "--------------------------------"
            )
            print(name)
            print(
                "--------------------------------"
            )

            try:
                response = client.get(
                    endpoint,
                    params=params,
                )

            except httpx.HTTPError as exc:
                print(
                    "Request error      : "
                    f"{exc}"
                )
                continue

            print(
                "Status             : "
                f"{response.status_code}"
            )
            print(
                "Final URL          : "
                f"{response.url}"
            )
            print(
                "Content-Type       : "
                f"{response.headers.get('content-type')}"
            )
            print(
                "Content length     : "
                f"{len(response.content)}"
            )

            body_preview = (
                response.text[:300]
                .replace("\n", " ")
                .replace("\r", " ")
            )

            print(
                "Body preview       : "
                f"{body_preview!r}"
            )

            if response.status_code != 200:
                continue

            try:
                payload = response.json()

            except json.JSONDecodeError:
                print(
                    "JSON               : NO"
                )
                continue

            print(
                "JSON               : YES"
            )

            inspect_json(payload)


if __name__ == "__main__":
    main()