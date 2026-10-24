# -*- coding: utf-8 -*-
# Part of gu_email_otp_login. See LICENSE file for full copyright and licensing details.

import hashlib
import hmac
import secrets
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import AccessDenied


class ResUsersOtp(models.Model):
    """One-Time Password (OTP) challenge used for password-less, email-based
    authentication.

    Each record represents a single OTP challenge issued to a user. Only a
    salted SHA-256 digest of the code is ever persisted: the plaintext OTP
    exists in memory only for the brief moment between generation and
    being handed off to the caller for delivery (e.g. by email), and is
    never written to the database or to the logs.

    All tuning parameters (code length, validity window, max attempts,
    resend cooldown, hourly request cap) are configurable per company via
    Settings > General Settings > Email OTP Login (see res.company),
    rather than fixed constants - every method below reads them from the
    relevant company record at call time.

    Lifecycle
    ---------
    ``pending``   OTP has been issued and is awaiting verification.
    ``verified``  OTP was successfully verified. Terminal state.
    ``expired``   OTP is no longer usable - either its validity window
                  passed, a newer OTP superseded it, or it exhausted its
                  verification attempts. Terminal state.
    """
    _name = 'res.users.otp'
    _description = 'User Email OTP (One-Time Password)'
    _order = 'create_date desc'
    _rec_name = 'user_id'

    user_id = fields.Many2one(
        comodel_name='res.users',
        string='User',
        required=True,
        ondelete='cascade',
        index=True,
        help='User this OTP challenge was issued for.',
    )
    login = fields.Char(
        related='user_id.login',
        string='Login',
        store=True,
        readonly=True,
        help='Denormalized login of the user, kept for easier auditing '
             'and search without joining res.users.',
    )
    otp_salt = fields.Char(
        string='Salt',
        required=True,
        readonly=True,
        help='Random salt used when hashing this OTP. A fresh salt is '
             'generated for every code, so identical codes never produce '
             'the same stored digest.',
    )
    otp_hash = fields.Char(
        string='OTP Hash',
        required=True,
        readonly=True,
        help='Salted SHA-256 digest of the OTP code. The plaintext code '
             'itself is never stored.',
    )
    expiration_date = fields.Datetime(
        string='Expires On',
        required=True,
        readonly=True,
        help='Timestamp after which this OTP can no longer be verified, '
             'even if the code is correct.',
    )
    attempt_count = fields.Integer(
        string='Verification Attempts',
        default=0,
        readonly=True,
        help='Number of failed verification attempts made against this '
             'OTP. Once it reaches the company-configured maximum, the '
             'OTP is expired automatically.',
    )
    state = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('verified', 'Verified'),
            ('expired', 'Expired'),
        ],
        string='Status',
        default='pending',
        required=True,
        readonly=True,
        index=True,
    )

    # ------------------------------------------------------------------
    # Hashing helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _hash_otp(otp, salt):
        """Return the hex-encoded salted SHA-256 digest of ``otp``.

        :param str otp: plaintext OTP code.
        :param str salt: random, per-record salt.
        :return: hex digest string.
        :rtype: str
        """
        message = f'{salt}{otp}'.encode('utf-8')
        return hashlib.sha256(message).hexdigest()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @api.model
    def _generate_otp(self, user):
        """Issue a new OTP challenge for ``user``.

        Code length and validity window are read from
        ``user.company_id`` at generation time, so a later change to
        those settings only affects OTPs generated afterwards - it never
        retroactively changes an already-issued, still-pending code.

        Any OTP still ``pending`` for this user is expired first, so only
        the most recently requested code is ever valid.

        :param res.users user: the user to issue the OTP to (single record).
        :return: the newly created OTP record and its plaintext code.
        :rtype: tuple(res.users.otp, str)
        """
        user.ensure_one()
        self._expire_pending(user)

        company = user.company_id
        code_length = company.otp_code_length
        validity_minutes = company.otp_validity_minutes

        plaintext_otp = ''.join(secrets.choice('0123456789') for _ in range(code_length))
        salt = secrets.token_hex(16)

        otp_record = self.sudo().create({
            'user_id': user.id,
            'otp_salt': salt,
            'otp_hash': self._hash_otp(plaintext_otp, salt),
            'expiration_date': fields.Datetime.now() + timedelta(minutes=validity_minutes),
            'state': 'pending',
        })
        return otp_record, plaintext_otp

    def _expire_pending(self, user):
        """Mark every still-``pending`` OTP of ``user`` as ``expired``.

        :param res.users user: user whose pending OTPs should be expired.
        """
        pending = self.sudo().search([
            ('user_id', '=', user.id),
            ('state', '=', 'pending'),
        ])
        if pending:
            pending.write({'state': 'expired'})

    def _verify(self, otp):
        """Verify a plaintext ``otp`` against this OTP record.

        :param str otp: the plaintext code submitted by the user.
        :raises AccessDenied: if the record is not pending, has expired,
            has exceeded its attempt budget, or the code does not match.
        """
        self.ensure_one()

        if self.state != 'pending':
            raise AccessDenied(_('This OTP is no longer valid. Please request a new one.'))

        if fields.Datetime.now() > self.expiration_date:
            self.sudo().write({'state': 'expired'})
            raise AccessDenied(_('This OTP has expired. Please request a new one.'))

        max_attempts = self.user_id.company_id.otp_max_attempts
        if self.attempt_count >= max_attempts:
            self.sudo().write({'state': 'expired'})
            raise AccessDenied(_('Too many incorrect attempts. Please request a new OTP.'))

        expected_hash = self._hash_otp(otp, self.otp_salt)
        # Constant-time comparison: avoids leaking timing information that
        # could otherwise help an attacker narrow down the digest.
        if not hmac.compare_digest(expected_hash, self.otp_hash):
            new_attempt_count = self.attempt_count + 1
            if new_attempt_count >= max_attempts:
                # This was the last chance - lock it out immediately, in
                # the same call, rather than waiting for one more
                # submission to notice the limit was reached.
                self.sudo().write({'attempt_count': new_attempt_count, 'state': 'expired'})
                raise AccessDenied(_('Too many incorrect attempts. Please request a new OTP.'))
            self.sudo().write({'attempt_count': new_attempt_count})
            raise AccessDenied(_('Incorrect OTP. Please try again.'))

        self.sudo().write({'state': 'verified'})

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------
    @api.model
    def _get_resend_wait_seconds(self, user):
        """Return how many seconds ``user`` must still wait before a new
        OTP may be requested for them, or 0 if they may request one now.

        Combines two independent, company-configurable limits:
        1. A short cooldown since the *last* request (anti-double-click).
        2. A rolling-window cap on *total* requests in the last hour
           (anti-abuse - stops indefinite patient clicking of "Resend").
        Whichever of the two demands the longer wait wins.

        :param res.users user: the user being checked.
        :return: seconds remaining, 0 if a new OTP may be sent right now.
        :rtype: int
        """
        user.ensure_one()
        company = user.company_id
        cooldown_seconds = company.otp_resend_cooldown_seconds
        max_per_hour = company.otp_max_requests_per_hour
        now = fields.Datetime.now()

        last = self.sudo().search([
            ('user_id', '=', user.id),
        ], order='create_date desc', limit=1)
        cooldown_wait = 0
        if last:
            elapsed = (now - last.create_date).total_seconds()
            cooldown_wait = max(0, int(cooldown_seconds - elapsed))

        window_start = now - timedelta(hours=1)
        recent = self.sudo().search([
            ('user_id', '=', user.id),
            ('create_date', '>=', window_start),
        ], order='create_date asc')
        cap_wait = 0
        if len(recent) >= max_per_hour:
            oldest_in_window = recent[0]
            cap_wait = max(0, int(((oldest_in_window.create_date + timedelta(hours=1)) - now).total_seconds()))

        return max(cooldown_wait, cap_wait)

    @api.autovacuum
    def _gc_expired_otps(self):
        """Periodic housekeeping, run by Odoo's standard autovacuum cron.

        1. A code that was requested but never used stays in the ``pending``
           state even after its validity window has passed. Mark those as
           ``expired``, so they are never reported as "pending" and become
           eligible for step 2.
        2. Delete OTP records that are no longer pending once they are more
           than 30 days old.

        The 30 days is how long records are kept for the dashboard's history;
        it is deliberately NOT tied to any company's ``otp_validity_minutes``,
        which is the security lifetime of a single code.
        """
        now = fields.Datetime.now()
        abandoned = self.sudo().search([
            ('state', '=', 'pending'),
            ('expiration_date', '<', now),
        ])
        if abandoned:
            abandoned.write({'state': 'expired'})
        cutoff = now - timedelta(days=30)
        self.sudo().search([
            ('state', '!=', 'pending'),
            ('create_date', '<', cutoff),
        ]).unlink()