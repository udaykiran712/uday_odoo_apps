# -*- coding: utf-8 -*-
# Part of auth_otp_login. See LICENSE file for full copyright and licensing details.

from datetime import timedelta

from odoo import api, fields, models


class AuthOtpUnregisteredLogin(models.Model):
    """Rate-limiting log for OTP requests against an email with no
    matching account.

    A real `res.users.otp` record can't be used for this path - it
    requires a genuine `user_id` (there is none for an email nobody
    registered) - so this lightweight sibling model exists purely to
    remember "when did we last notify this address that it isn't
    registered", so that path gets its own independent cooldown, exactly
    like real OTP resends do, rather than being unthrottled.

    Since there is no matching user (and therefore no unambiguous
    company), the rate-limit settings applied here come from whichever
    company is passed in by the caller, falling back to the current
    environment's default company if none is given.

    No verification, no hashing, nothing security-sensitive lives here -
    just an email string and a timestamp, purely for abuse prevention.
    """
    _name = 'auth.otp.unregistered.login'
    _description = 'Unregistered-Email OTP Request Log (rate limiting only)'
    _order = 'create_date desc'
    _rec_name = 'login'

    login = fields.Char(
        required=True,
        index=True,
        readonly=True,
        help='The email/login that was typed but does not match any '
             'existing account.',
    )

    @api.model
    def _get_resend_wait_seconds(self, login, company=None):
        """Seconds left before ``login`` may be notified again, or 0 if
        it's safe to send a notice now.

        :param str login: the email address being checked.
        :param res.company company: company whose rate-limit settings
            apply; defaults to the current environment's company.
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
        """Record that a not-registered notice was just sent to ``login``."""
        return self.sudo().create({'login': login})

    @api.autovacuum
    def _gc_old_attempts(self):
        """Periodically delete old log rows (same pattern as res.users.otp)."""
        cutoff = fields.Datetime.now() - timedelta(days=30)
        stale = self.sudo().search([('create_date', '<', cutoff)])
        stale.unlink()
