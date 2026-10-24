# -*- coding: utf-8 -*-
# Part of gu_email_otp_login. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import api, fields, models


class AuthOtpRestrictedLogin(models.Model):
    """Rate-limiting log for OTP requests made by a real, existing user
    who is excluded from OTP login by the company's group policy (see
    `res.company.otp_login_blocked_group_ids`).

    Deliberately a separate, precisely-named model from
    `auth.otp.unregistered.login`: "no account exists for this email"
    and "an account exists but OTP isn't enabled for it" are different
    facts, and conflating them under one model name would be misleading
    to anyone reading this code later.
    """
    _name = 'auth.otp.restricted.login'
    _description = 'Restricted-User OTP Request Log (rate limiting only)'
    _order = 'create_date desc'
    _rec_name = 'login'

    login = fields.Char(
        required=True,
        index=True,
        readonly=True,
        help='The email/login of a real user who is not permitted to '
             'use OTP login under the current group restriction.',
    )

    @api.model
    def _get_resend_wait_seconds(self, login, company=None):
        """Seconds left before ``login`` may be notified again, or 0 if
        it's safe to send a notice now.

        :param str login: the email address being checked.
        :param res.company company: company whose rate-limit settings
            apply; defaults to the current environment's company. The
            caller normally has the real matching user on hand (this
            model only ever applies to a real, existing user) and should
            pass that user's actual company for accuracy.
        """
        company = company or self.env.company
        cooldown_seconds = company.otp_resend_cooldown_seconds
        max_per_hour = company.otp_max_requests_per_hour
        now = fields.Datetime.now()

        last = self.sudo().search([('login', '=', login)], order='create_date desc', limit=1)
        cooldown_wait = 0
        if last:
            elapsed = (now - last.create_date).total_seconds()
            cooldown_wait = max(0, int(cooldown_seconds - elapsed))

        window_start = now - timedelta(hours=1)
        recent = self.sudo().search([
            ('login', '=', login),
            ('create_date', '>=', window_start),
        ], order='create_date asc')
        cap_wait = 0
        if len(recent) >= max_per_hour:
            oldest_in_window = recent[0]
            cap_wait = max(0, int(((oldest_in_window.create_date + timedelta(hours=1)) - now).total_seconds()))

        return max(cooldown_wait, cap_wait)

    @api.model
    def _log_attempt(self, login):
        """Record that a not-allowed notice was just sent to ``login``."""
        return self.sudo().create({'login': login})

    @api.autovacuum
    def _gc_old_attempts(self):
        """Periodically delete old log rows (same pattern as its siblings)."""
        cutoff = fields.Datetime.now() - timedelta(days=30)
        stale = self.sudo().search([('create_date', '<', cutoff)])
        stale.unlink()
