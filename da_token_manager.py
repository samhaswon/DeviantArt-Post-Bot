import binascii
import json
import requests
import random
import string
import time
from typing import Union
import webbrowser

import oauth_handler


class HTTPBasicAuth:
    __slots__ = ("authorization",)

    def __init__(self, username, password):
        self.authorization = b"Basic " + binascii.b2a_base64(
            username.encode("latin1") + b":" + str(password).encode("latin1")
        )[:-1]

    def __call__(self, request):
        request.headers["Authorization"] = self.authorization
        return request


class DATokenManager:
    """
    Class to keep the access __token from DeviantArt up to date
    """

    def __init__(self, config: dict, debug: bool = False):
        """
        :param config: A dict with keys `client_id` and `client_secret` for the DA API
        :param debug: Whether to print extra debugging information returned from the DeviantArt API.
        """
        # A.k.a. `access_token`
        self.__token: Union[str, None] = None
        # When `self.__token` expires
        self.token_expiry_time: Union[float, None] = None
        # Debug flag
        self.__debug: bool = debug
        # Application `client_id`
        self.__client_id: str = config["client_id"]
        # Application `client_secret`
        self.__client_secret: str = config["client_secret"]
        # OAuth token, if we're using it.
        self.__oauth_token: Union[str, None] = config.get("oauth_token", None)
        # Refresh token for OAuth stuff
        self.__refresh_token: Union[str, None] = config.get("refresh_token", None)
        # Config in the config that is not used by the token manager.
        self.__extra_config: dict = {}

        # Extract extra config
        for key in config.keys():
            if (key not in
                    {"client_id",
                     "client_secret",
                     "oauth_token",
                     "refresh_token"}):
                self.__extra_config[key] = config[key]

        # Get needed tokens
        if self.__oauth_token is not None or self.__refresh_token is not None:
            self.refresh_token()
        else:
            self.get_oauth_token()

    @property
    def token(self) -> str:
        """
        Get the current token for the API.
        :return: The `access_token` for the API.
        """
        if self.__token is None or time.time() >= self.token_expiry_time:
            self.refresh_token()
        else:
            self.save_config()
        return self.__token

    @property
    def extra_config(self) -> dict:
        """
        All other information that is a part of the configuration not needed for this.
        :return: The other config information.
        """
        return self.__extra_config

    def increment_rotation_config(self, post_type, value) -> None:
        """
        Updates the value of rotation configurations.
        :param post_type: The post type to update.
        :param value: The new rotation value.
        :return: None.
        """
        if post_type in self.__extra_config["post_config"] and \
                self.__extra_config["post_config"][post_type]["type"] == "rotation":
            self.__extra_config["post_config"][post_type]["last_posted"] = value
        else:
            raise RuntimeError(f"Invalid post config type or post type")

    def refresh_token(self) -> None:
        """
        Refreshes the access token for the API
        :return: None
        """
        # Make the API call to get a new token
        try:
            self.__token = self._get_new_token_from_api()
        # If the connection fails to be established, try again. This could exceed recursion depth.
        except requests.exceptions.ConnectionError or requests.exceptions.HTTPError:
            # Wait a few seconds for DNS to be happier
            time.sleep(5)
            self.refresh_token()
            return
        self.token_expiry_time = time.time() + 3600
        if self.__debug:
            print(f"Token refreshed: {self.__token=}")
        self.save_config()

    def _get_new_token_from_api(self) -> str:
        """
        Retrieves a new access token from DA.
        :return: New `access_token`
        """
        if self.__refresh_token is None:
            auth_parameters = HTTPBasicAuth(self.__client_id, self.__client_secret)
            data = {
                "grant_type": "authorization_code",
                "redirect_uri": "https://mikf.github.io/gallery-dl/oauth-redirect.html",
                "code": self.__oauth_token
            }
            auth_result = requests.post(" https://www.deviantart.com/oauth2/token",
                                        auth=auth_parameters,
                                        data=data)
            if auth_result.status_code > 399:
                raise RuntimeError(f"Error with authentication {auth_result.status_code} {auth_result.reason}\n"
                                   f"{auth_result.text}")
            if self.__debug:
                print(f"{auth_result=}")
            result_json = auth_result.json()
            if "error" in result_json:
                raise RuntimeError(f"Error getting credentials: {result_json['error_description']}")

            self.__refresh_token = result_json.get("refresh_token", None)

            return result_json["access_token"]
        else:
            auth_parameters = HTTPBasicAuth(self.__client_id, self.__client_secret)
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.__refresh_token
            }
            auth_result = requests.post(" https://www.deviantart.com/oauth2/token",
                                        auth=auth_parameters,
                                        data=data)
            if auth_result.status_code > 399:
                raise RuntimeError(f"Error with authentication {auth_result.status_code} {auth_result.reason}\n"
                                   f"{auth_result.text}")
            if self.__debug:
                print(f"{auth_result=}")
            result_json = auth_result.json()
            if "error" in result_json:
                raise RuntimeError(f"Error getting credentials: {result_json['error_description']}")

            self.__refresh_token = result_json.get("refresh_token", self.__refresh_token)
            if self.__debug:
                print(f"{self.__refresh_token=}")

            return result_json["access_token"]

    def get_oauth_token(self) -> str:
        """
        Gets a new OAuth token for use with the API.
        :return: New token.
        """
        # Make a Nonce
        nonce = "".join(random.choice(string.ascii_letters) for _ in range(30))
        # Open the OAuth link for the user to authorize the application
        webbrowser.open(
            f"https://www.deviantart.com/join?referer=https%3A%2F%2Fwww.deviantart.com%2Foauth2%2Fauthorize"
            f"%3Fresponse_type%3Dcode%26redirect_uri%3Dhttps%253A%252F%252Fmikf.github.io%252Fgallery-dl%252Foauth"
            f"-redirect.html%26scope%3Dbasic%26state%3D{nonce}%26client_id%3D{self.__client_id}&oauth=1",
            new=2, autoraise=True
        )

        # Start the receiving server
        oauth_handler.run()

        # Handle OAuth results
        if self.__debug:
            print(f"OAuth Results: \n"
                  f"{oauth_handler.state=} ({nonce=})\n"
                  f"{oauth_handler.code=}")
        if oauth_handler.state != nonce:
            raise RuntimeError(f"Possible MITM! Nonce and state do NOT match!\n"
                               f"| {nonce=} | {oauth_handler.state=} |")

        self.__oauth_token = oauth_handler.code
        return oauth_handler.code

    def save_config(self) -> None:
        """
        Saves the configuration (likely with an updated token) to the configuration file.
        :return:
        """
        with open("da_config.json", "w") as json_file:
            json_file.write(self.__str__())
        if self.__debug:
            print("Saved config")

    def __str__(self):
        """
        Prints the configuration of the token manager as a string.
        :return:
        """
        config_dict = {
            "client_id": int(self.__client_id),
            "client_secret": self.__client_secret,
            "refresh_token": self.__refresh_token,
            **self.__extra_config
        }
        return json.dumps(config_dict, indent=4)
