#!/usr/bin/env sh
set -e

if [ ! -d /signald-sock ]; then
    echo "The /signald-sock directory does not exist. Please attach it properly and run the setup script."
    exit 1
fi
signaldctl config set socketpath /signald-sock/signald.sock

URL="https://signalcaptchas.org/registration/generate"
URL2="https://signald.org/articles/captcha/"
read -p "Generate a captcha at $URL (see $URL2 for more info) and enter the token: " token
# drop the prefix "signalcaptcha://" if present
token=${token#signalcaptcha://}
signaldctl account register $BOT_NUMBER --captcha $token
read -p "Enter your 2FA code: " code
signaldctl account verify $BOT_NUMBER $code
touch /signald-sock/setup_completed
echo "Setup completed."
