# Setup

Go [here](https://www.deviantart.com/developers/) and click "Register your Application" to begin. 

Set OAuth2 Grant Type to "Authorization Code" and the Redirect URI Whitelist to `https://mikf.github.io/gallery-dl/oauth-redirect.html`.
Basically, this page redirects to the server started by [oauth_handler.py](./oauth_handler.py) to get the key used by the application. 
There's also a nonce check to help ensure some level of integrity in the communication.

Go back [here](https://www.deviantart.com/developers/) to retrieve the `client_id` and the `client_secret` to be placed into [da_config.json](./da_config.json)
