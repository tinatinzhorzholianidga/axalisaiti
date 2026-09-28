# Outgoing email (verification links, password resets)

The platform sends three kinds of email: the **verification link** after
registration (when *Require email verification* is on), the **password
reset link** from "Forgot password", and a **welcome / password changed**
notice. All of them go out through one SMTP account, queued by the web
container and delivered by the `worker` container (Celery), and are written
in the language the user was using.

## 1. Put the SMTP account in `.env`

```
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USE_SSL=false
MAIL_USERNAME=your.address@gmail.com
MAIL_PASSWORD=abcd efgh ijkl mnop      # a Gmail *app password*, not your login password
MAIL_DEFAULT_SENDER=your.address@gmail.com
MAIL_SUPPRESS_SEND=false
```

* **Gmail / Google Workspace**: turn on 2-step verification for the account,
  then create an app password at https://myaccount.google.com/apppasswords and
  paste the 16 characters as `MAIL_PASSWORD`. The sender must be that address
  (or an alias of it).
* **Office 365 / Outlook**: `smtp.office365.com`, port 587, TLS on, the
  mailbox's own credentials; SMTP AUTH must be enabled for the mailbox.
* **Own mail server (gov.ge relay)**: ask the mail team for host, port and
  whether STARTTLS (port 587, `MAIL_USE_TLS=true`) or SSL (port 465,
  `MAIL_USE_SSL=true`, `MAIL_USE_TLS=false`) is used, and which sender
  addresses the relay accepts.

`MAIL_SUPPRESS_SEND=false` is what actually turns sending on; the local
compose override keeps it off unless `.env` says otherwise.

## 2. Restart and test

```
sudo docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
sudo docker compose exec web flask --app wsgi:app send-test-email --to you@example.org
```

The command prints `Sent to …` or the exact SMTP error (wrong password, port
blocked, sender rejected). The same test is available in the admin panel:
*Platform → Site settings → Outgoing email → Send a test email*.

## 3. Switch verification on

*Admin → Site settings → Require email verification.* From then on a new
account must open the link from the email before it can sign in; the login
page offers "Resend the verification email". Accounts created before the
switch stay usable. "Forgot password" works whether or not verification is
required.

## Links in the emails

Links are built from the address the visitor used (`https://learn.example.org/…`).
Behind nginx that works because the proxy forwards `X-Forwarded-Proto` and
`X-Forwarded-Host` and the app trusts one proxy hop (`BEHIND_PROXY=true`, the
default). If the app runs without a reverse proxy, set `BEHIND_PROXY=false`.

## Troubleshooting

* `SMTPAuthenticationError` on Gmail: use an app password, not the account
  password; 2-step verification must be on.
* `Connection refused` / timeout on port 587: the host's firewall or the
  hosting provider blocks outgoing SMTP; try port 465 with SSL, or a relay.
* Messages land in spam: set `MAIL_DEFAULT_SENDER` to an address on a domain
  with SPF/DKIM for that SMTP provider.
* Nothing arrives and no error: check that the `worker` container is up
  (`docker compose ps`) and its logs (`docker compose logs worker`).
