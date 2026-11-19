"""Plaid client (read only): link, accounts and transactions. Everything goes through the guard."""


class PlaidClient:
    def __init__(self, http, settings):
        self.http, self.s = http, settings
        host = "sandbox" if settings.plaid_env == "sandbox" else "production"
        self.base = f"https://{host}.plaid.com"
        self._names: dict[str, str] = {}

    def _post(self, path: str, **body) -> dict:
        body = {"client_id": self.s.plaid_client_id, "secret": self.s.plaid_secret, **body}
        r = self.http.request("plaid", "POST", self.base + path, json=body)
        r.raise_for_status()
        return r.json()

    def link_token_create(self) -> dict:
        j = self._post(
            "/link/token/create",
            client_name="daily agent",
            language="en",
            country_codes=["US"],
            user={"client_user_id": "1"},
            products=["transactions"],
            hosted_link={},
        )
        return {"link_token": j["link_token"], "hosted_link_url": j.get("hosted_link_url")}

    def link_token_public_token(self, link_token: str) -> str | None:
        """Public token once the hosted screen is finished, else None."""

        def find(x):
            if isinstance(x, dict):
                if x.get("public_token"):
                    return x["public_token"]
                x = list(x.values())
            if isinstance(x, list):
                for v in x:
                    if (r := find(v)) is not None:
                        return r
            return None

        return find(self._post("/link/token/get", link_token=link_token))

    def sandbox_public_token(self) -> str:
        j = self._post(
            "/sandbox/public_token/create",
            institution_id="ins_109508",  # First Platypus Bank, a fake bank
            initial_products=["transactions"],
        )
        return j["public_token"]

    def exchange(self, public_token: str) -> tuple[str, str]:
        j = self._post("/item/public_token/exchange", public_token=public_token)
        return j["access_token"], j["item_id"]

    def accounts(self, access_token: str) -> tuple[str, str, list[dict]]:
        j = self._post("/accounts/get", access_token=access_token)
        inst = j["item"].get("institution_id") or ""
        if inst and inst not in self._names:
            i = self._post("/institutions/get_by_id", institution_id=inst, country_codes=["US"])
            self._names[inst] = i["institution"]["name"]
        return inst, self._names.get(inst, ""), j["accounts"]

    def transactions_sync(self, access_token: str, cursor: str | None) -> dict:
        extra = {"cursor": cursor} if cursor else {}
        return self._post("/transactions/sync", access_token=access_token, count=500, **extra)

    def item_remove(self, access_token: str) -> None:
        self._post("/item/remove", access_token=access_token)
