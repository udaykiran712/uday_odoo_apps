# -*- coding: utf-8 -*-
# Part of auth_otp_login. See LICENSE file for full copyright and licensing details.
{
    'name': 'Email OTP Login',
    'version': '18.0.1.0.0',
    'category': 'Extra Tools',
    'summary': 'Password-less login with a One-Time Password sent by email',
    'description': """
Email OTP Login
===============
Let your users sign in without typing a password at all.

How it works
------------
* The user enters their email on the login screen and clicks
  **"Login with Email OTP"**.
* A 6-digit, single-use code is generated and emailed to them.
* The user enters the code on the same screen and is logged in directly,
  without ever needing to type (or even have) a password.

Why use it
----------
* **Faster onboarding** - no password to invent, remember, or reset.
* **Stronger by default** - codes are short-lived, single-use, hashed at
  rest, and rate-limited against brute-force attempts.
* **Non-intrusive** - existing password login keeps working exactly as
  before. OTP is offered as an additional option, not a replacement.
* **Simple setup** - needs only a working outgoing mail server and an email
  address on your company (used as the sender); no external service or API
  key required.

Security highlights
--------------------
* OTP codes are never stored in plain text (salted SHA-256 digest only).
* Each OTP is valid for a short, configurable window and can only be
  used once.
* Verification attempts are capped per code to prevent guessing.
* Requesting a new OTP automatically invalidates any previous one for
  that user.
    """,
    'author': 'Gardas Udaykiran',
    'website': 'https://github.com/udaykiran712',
    'license': 'LGPL-3',
    'images': ['static/description/banner.png'],
    'depends': [
        'base',
        'base_setup',
        'web',
        'mail',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/mail_template_otp.xml',
        'data/mail_template_otp_unknown.xml',
        'data/mail_template_otp_not_allowed.xml',
        'views/login_templates.xml',
        'views/res_config_settings_views.xml',
        'views/dashboard_templates.xml',
        'views/dashboard_menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}