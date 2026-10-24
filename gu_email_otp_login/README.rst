===============
Email OTP Login
===============

Password-less login for Odoo 18. Users sign in with a one-time code sent to
their email: no password to remember, reset or leak.

Password login keeps working exactly as before. "Login with Email OTP" is an
extra option on the standard Odoo login page, not a replacement.

**Table of contents**

.. contents::
   :local:

Features
========

* Request a code by email, type it into auto-advancing digit boxes, and sign in.
* Codes are single-use, short-lived and stored only as a salted SHA-256 digest.
* Attempt limit per code, resend cooldown and a rolling hourly cap per address.
* The login page answers identically for existing, unknown and blocked
  addresses, so it cannot be used to discover which emails have accounts.
* Block specific user groups from OTP login (for example, make it portal-only).
* Works with Odoo's two-factor authentication: users who have it enabled are
  still asked for their authenticator code after the OTP.
* Per-company settings, so each company has its own limits and sender address.
* A live security dashboard for administrators.
* Designed notification emails: the code, "no account for this email", and
  "OTP login isn't available for your account".

Installation
============

#. Install **Email OTP Login** from Apps.
#. Make sure Odoo can send email: configure an outgoing mail server and set an
   email address on your company. That address is used as the sender.
#. Open your login page and click **Login with Email OTP**.

Configuration
=============

Go to *Settings → General Settings → Email OTP Login*. Settings are stored per
company and every value is range-checked on save.

.. list-table::
   :header-rows: 1
   :widths: 30 40 15 15

   * - Setting
     - What it controls
     - Default
     - Allowed
   * - Who is blocked from OTP login
     - User groups that cannot use OTP login
     - No one
     - Any groups
   * - Code length
     - Digits in each code
     - 6
     - 4 - 10
   * - Code validity
     - Minutes a code stays valid
     - 10
     - 1 - 60
   * - Max verification attempts
     - Wrong guesses allowed per code
     - 5
     - 1 - 20
   * - Resend cooldown
     - Seconds between two requests for one address
     - 30
     - 10 - 3600
   * - Max requests per hour
     - Rolling hourly cap per address
     - 5
     - 1 - 100

Usage
=====

#. On the login page, click **Login with Email OTP** and enter your email.
#. Enter the code from the email into the digit boxes.
#. You are signed in. If you have two-factor authentication enabled, Odoo then
   asks for your authenticator code.

Administrators can open the dashboard from *Settings → OTP Security*.

Security
========

* Codes are generated with Python's ``secrets`` module.
* Only a salted SHA-256 digest is stored, with a fresh random salt per code.
* Codes are compared in constant time (``hmac.compare_digest``).
* A code is single-use; requesting a new one invalidates the previous one.
* A code locks the moment its last attempt is used.
* Blocked groups are checked when a code is requested and again when it is
  verified.

Privacy and data
================

For each code the module stores the user, the login that was typed, a random
salt, the salted hash of the code, its expiry, the attempt count and its state.
For addresses with no matching account, and for users in a blocked group, it
stores the typed email and a timestamp (used for rate limiting and the
dashboard).

All of this stays in your own Odoo database and is deleted automatically after
30 days. The module makes no outbound network requests of its own; the only
thing that leaves your server is the email itself, sent through your own
outgoing mail server.

Requirements
============

* Odoo 18.0 (built and tested on Community).
* Depends only on the standard modules ``base``, ``base_setup``, ``web`` and
  ``mail``. No extra Python packages.
* A working outgoing mail server and an email address on the company.
* Odoo.sh or on-premise. Custom apps cannot be installed on Odoo Online.

Credits
=======

Author: Gardas Udaykiran

* Odoo Apps: https://apps.odoo.com/apps/browse?repo_maintainer_id=1184648
* GitHub: https://github.com/udaykiran712/uday_odoo_apps
* LinkedIn: https://www.linkedin.com/in/udaykirangardas/

License
=======

LGPL-3