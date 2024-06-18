<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/Wheest/signal-bot">
    <img src="logo.png" alt="Logo" width="80" height="80">
  </a>

  <h3 align="center">Signal Bot</h3>

  <p align="center">
    An extensible Signal bot with various utilities
    <br />
  </p>
</div>

Note this repo is not an official product of the Signal Technology Foundation.

## Design


## Setup

To use the bot, you need to have a phone number that the bot can use to send and receive messages.
We then need to set up a Signal account for the bot to use.
This uses the `signald` library, which is a Signal client that can be run in headless mode.
This setup only needs to be done once per installation, with the configuration saved in a bind-mounted volume (under `signald-config`, so it persists across container restarts).

There several environment variables that need to be set in the various `.env` files in the `config` directory.[^1]
Examples are given, be sure to remove the `.example` extension from the file name.

`phone.env` is used to set the phone number of the bot and is used by `signald`, and `bot.env` is used to set the API keys and other configuration variables and is used by our Python bot scripts.

The `BOT_NUMBER` is the phone number that the bot will use to send and receive messages.
`BOT_ADMIN_NUMBER` is the phone number of the bot admin, who can use admin commands.
Note that sometimes the bot will not be able to get the phone number of the sender, and will instead fallback to the UUID of the sender.
For this case, there is also an optional `BOT_ADMIN_UUID` variable, which is the UUID of the bot admin.
The `/show-uuid` command can be used to get the UUID of a user.

You will also need to edit some of the configuration files in the `config` directory.
For example, you need an `allowlist.json` file to specify which numbers or groups are allowed to use the bot.
You should add your own number to this file, so you can test the bot.
To get the group ID of a group, check the `signald` logs when the bot is added to the group.

`username.json` is used to map usernames to phone numbers, so you can use the bot will know what name to use when replying to a message.


First run just the signald container, then attach to, executing the setup script:

``` sh
docker compose up -d signald --build
docker exec -it signal-bot-docker-signald-1 /bin/sh -c "/signald_setup.sh"
```

You will need to enter a captcha, which you complete online ([see here for details](https://signald.org/articles/captcha/)), and then fill in a 2FA code, which will be sent to the phone number you provided.
Once this is complete, you should then be able to run the full system with:

``` sh
docker compose up
```

If everything works, you could be able to test your bot by messaging it on Signal.
The `/echo` or `/help` commands have minimal dependencies.


Send a message to your test number:


### Minecraft server

The bot can also be used to manage a Minecraft server.
The configuration for the server is in the `config/mineraft.json` file.
You also need to AWS credentials in `config/aws.env`.
TODO: Add more details here.

[^1]: Using envionment variables for API keys is not recommended for production use, as they can be easily exposed. For production use, you should use a secrets manager or similar.
