# Google reCAPTCHA

The public forms (create account, forgot password, resend verification) show
Google's "I'm not a robot" checkbox, and the sign-in form shows it after two
failed attempts in the same browser. The widget, its picture challenge and the
check of the answer are Google's; the app only passes the token on to Google
and reads the verdict.

## 1. Get the keys

1. Open <https://www.google.com/recaptcha/admin> with a Google account.
2. Register a site: **reCAPTCHA v2 → "I'm not a robot" Checkbox**.
3. Add every domain the site is served from, for example `learn.example.gov.ge`
   and, for a local trial, `localhost`.
4. Copy the **site key** (public, goes to the browser) and the **secret key**
   (server only).

## 2. Put them in `.env`

```
RECAPTCHA_SITE_KEY=6Lc...
RECAPTCHA_SECRET_KEY=6Lc...
```

Recreate the containers so they pick the values up (`restart` keeps the old
environment):

```
sudo docker compose -f docker-compose.yml -f docker-compose.local.yml up -d
```

*Admin → Site settings → Security check* shows whether the keys are in place.
Without keys the forms show no widget and nothing is checked.

## 3. Switch and threshold

In *Admin → Site settings*:

* **Google reCAPTCHA on registration and password forms** switches the check
  off without touching the keys.
* **Ask for the reCAPTCHA check at sign-in after this many failed attempts**:
  `2` by default, `0` asks on every sign-in.

## What it means for the browser

The checkbox is a script and an iframe from `www.google.com` / `www.gstatic.com`.
While the keys are configured the Content-Security-Policy allows exactly those
origins in `script-src` and `frame-src`, and the `Cross-Origin-Embedder-Policy`
header is not sent (the challenge iframe would otherwise be refused). Google
receives the visitor's IP address and browser details when the widget loads;
say so in the privacy notice.

## Troubleshooting

* **"ERROR for site owner: Invalid key type"** (shown inside the widget): the
  key was created as a different type. The site uses the classic **v2 →
  "I'm not a robot" Checkbox**; a score-based (v3) key, a v2 *Invisible* key
  or a reCAPTCHA Enterprise key from the Google Cloud console all fail this
  way. Create a new key of the right type and replace both values in `.env`.
* **"Invalid site key" / "Localhost is not in the list of supported domains"**:
  add the domain in the reCAPTCHA admin console.
* **"The security check could not be verified right now."**: the server could
  not reach `https://www.google.com/recaptcha/api/siteverify`. The check fails
  closed on purpose; check outbound access from the `web` container.
* **"The security check failed."**: Google rejected the token (expired, reused,
  or the secret key does not match the site key). Keys are logged in the app
  log as `reCAPTCHA rejected a token: <error codes>`.

For local development without keys, leave both empty: the forms simply work
without the checkbox.
