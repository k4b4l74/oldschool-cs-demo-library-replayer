# Security

The app runs on your PC only: its server listens on `127.0.0.1`, and requests that change something must come from the app's own pages (`X-Oldschool` header and same-site origin). It reads archives and demos from many sources, so problems in how it opens files matter too.

## Reporting a vulnerability

Please report it privately: on GitHub, open the **Security** tab of this repository and choose **Report a vulnerability**. Do not open a public issue.

Say what an attacker could do and how (a sample file or the steps). You will get an answer as soon as possible, and credit in the release notes if you wish.

## Supported versions

Only the latest release gets fixes.
