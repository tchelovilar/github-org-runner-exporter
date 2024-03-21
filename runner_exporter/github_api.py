import requests
import logging
import time
import json
import jwt
import datetime

from dateutil import tz
from prometheus_client import Gauge


class githubApi:
    app_token = None
    app_token_expire_at = None
    # The number of minutes before the token should be renewed
    renew_token_minutes = 5

    def __init__(
        self,
        github_owner: str,
        logger: logging,
        github_token: str = None,
        github_app_id: str = None,
        private_key: str = None,
        api_url: str = "https://api.github.com",
    ) -> None:

        if github_owner is None or github_owner.strip() == "":
            raise ValueError("Github owner should not be empty")

        self.metric_runner_api_ratelimit = Gauge(
            "github_runner_api_remain_rate_limit",
            "Github Api remaining requests rate limit (per hour)",
            ["org"],
        )

        self.github_token = github_token
        self.github_app_id = github_app_id
        self.private_key = private_key
        self.github_owner = github_owner
        self.api_url = api_url
        self.logger = logger

    def app_jwt_header(self):
        """
        Creates a JSON Web Token (JWT) for authorization to be used with the GitHub API.
        The JWT includes the current time, an expiration time (10 minutes from the current time), and the GitHub app ID.
        The JWT is signed with the private key provided in the class constructor.

        Returns:
            dict: A dictionary containing the JWT header
        """
        time_since_epoch_in_seconds = int(time.time())
        payload = {
            "iat": time_since_epoch_in_seconds,
            "exp": time_since_epoch_in_seconds + (600),
            "iss": self.github_app_id,
        }

        actual_jwt = jwt.encode(payload, self.private_key, algorithm="RS256")

        return {
            "Authorization": "Bearer {}".format(actual_jwt),
            "Accept": "application/vnd.github.machine-man-preview+json",
        }

    def get_app_token(self):
        """
        Retrieves an app token for use with the GitHub API.
        If the app token is still valid (as determined by the `app_token_expire_at` attribute and the `token_renew_minutes` attribute),
        the existing token is returned. Otherwise, a new token is generated and returned.

        Returns:
            str: The app token for use with the GitHub API
        """
        if self.app_token_expire_at:
            expires_at = datetime.datetime.strptime(
                self.app_token_expire_at, "%Y-%m-%dT%H:%M:%SZ"
            )
            expires_at = expires_at.replace(tzinfo=tz.tzutc())
            now = datetime.datetime.now(tz.tzutc())
            if not expires_at - now < datetime.timedelta(
                minutes=self.renew_token_minutes
            ):
                self.logger.debug("The current app token still valid.")
                return self.app_token

        jwt_headers = self.app_jwt_header()

        try:
            instalations_response = requests.get(
                f"{self.api_url}/app/installations", headers=jwt_headers
            )
            instalations_response.raise_for_status()
            instalations = instalations_response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error("An error occured while getting app installations: %s", e)
            raise

        try:
            resp = requests.post(
                f'{self.api_url}/app/installations/{instalations[0]["id"]}/access_tokens',
                headers=jwt_headers,
            )
            resp.raise_for_status()
            token_data = json.loads(resp.content)
        except requests.exceptions.RequestException as e:
            self.logger.error("An error occured while getting app token: %s", e)
            raise

        self.app_token_expire_at = token_data["expires_at"]
        self.app_token = token_data["token"]
        self.logger.info(
            f"A new app token has been generated. It will expire on {self.app_token_expire_at}"
        )

        return token_data["token"]

    def get_headers(self):
        """
        Retrieves the headers for use with the GitHub API.
        If a GitHub token is provided, it is used as the "Authorization" header.
        If GitHub app ID is provided, an app token is generated and used as the "Authorization" header.

        Returns:
            dict: A dictionary containing the headers for use with the GitHub API

        Raises:
            ValueError: If neither a GitHub token nor a GitHub app ID is provided
        """
        headers = {}

        if self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        elif self.github_app_id:
            headers["Authorization"] = f"token {self.get_app_token()}"
        else:
            raise ValueError(
                "No token or app ID provided, a Github token or GitHub app is required."
            )

        return headers

    def list_runners(self) -> list:
        """
        Retrieves a list of the registered organization GitHub runners

        Returns:
            list: A list containing the current registered runners
        """
        runners_list = []

        headers = self.get_headers()

        per_page = 100
        url = f"https://api.github.com/orgs/{self.github_owner}/actions/runners?per_page={per_page}"

        while True:
            try:
                self.logger.debug(f"Sending the api request for {url}")
                result = requests.get(url, headers=headers)

                if result.headers:
                    remaining_requests = result.headers.get("X-RateLimit-Remaining")
                    self.logger.debug(f"Remaining requests: {remaining_requests}")
                    self.metric_runner_api_ratelimit.labels(self.github_owner).set(
                        int(remaining_requests)
                    )

                if not result.ok:
                    self.logger.error(
                        f"Api request returned error: {result.reason} {result.text}"
                    )
                    return []

                api_result = result.json()
                runners_list += api_result["runners"]

                if "next" in result.links.keys():
                    url = result.links["next"]["url"]
                else:
                    break
            except Exception as error:
                self.logger.error(f"Exception: {error}")
                return []

        return runners_list
