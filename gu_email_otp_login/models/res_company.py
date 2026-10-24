# -*- coding: utf-8 -*-
# Part of gu_email_otp_login. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResCompany(models.Model):
    _inherit = 'res.company'

    otp_login_blocked_group_ids = fields.Many2many(
        comodel_name='res.groups',
        relation='res_company_otp_login_blocked_group_rel',
        string='Groups Blocked from OTP Login',
        help='Users who belong to any of these groups will NOT see or be '
             'able to use the "Login with Email OTP" option - they must '
             'use their password instead. Leave empty to allow every '
             'user (the default). This is a block-list, not an '
             'allow-list: a new group created later is never silently '
             'excluded - only groups explicitly listed here are.',
    )

    otp_code_length = fields.Integer(
        string='OTP Code Length',
        default=6,
        help='Number of digits in each generated OTP code.',
    )
    otp_validity_minutes = fields.Integer(
        string='OTP Validity (minutes)',
        default=10,
        help='How long a generated OTP code stays valid after being sent, '
             'in minutes.',
    )
    otp_max_attempts = fields.Integer(
        string='Max Verification Attempts',
        default=5,
        help='Number of incorrect verification attempts allowed against a '
             'single OTP code before it is locked out and a new one must '
             'be requested.',
    )
    otp_resend_cooldown_seconds = fields.Integer(
        string='Resend Cooldown (seconds)',
        default=30,
        help='Minimum time that must pass between two consecutive OTP '
             'requests for the same email address.',
    )
    otp_max_requests_per_hour = fields.Integer(
        string='Max Requests Per Hour',
        default=5,
        help='Maximum number of OTP requests allowed for a single email '
             'address within any rolling 60-minute window - independent '
             'of, and in addition to, the resend cooldown above.',
    )

    @api.constrains('otp_code_length', 'otp_validity_minutes', 'otp_max_attempts',
                    'otp_resend_cooldown_seconds', 'otp_max_requests_per_hour')
    def _check_otp_settings(self):
        """Keep every OTP tuning value within a sane, safe range.

        These are security parameters, not cosmetic preferences - an
        admin fat-fingering "0" into any of these could otherwise lock
        every user out of OTP login, or make it trivially guessable, so
        each is bounded explicitly rather than trusted blindly.
        """
        for company in self:
            if not (4 <= company.otp_code_length <= 10):
                raise ValidationError(_('OTP code length must be between 4 and 10 digits.'))
            if not (1 <= company.otp_validity_minutes <= 60):
                raise ValidationError(_('OTP validity must be between 1 and 60 minutes.'))
            if not (1 <= company.otp_max_attempts <= 20):
                raise ValidationError(_('Maximum verification attempts must be between 1 and 20.'))
            if not (10 <= company.otp_resend_cooldown_seconds <= 3600):
                raise ValidationError(_('Resend cooldown must be between 10 seconds and 1 hour (3600 seconds).'))
            if not (1 <= company.otp_max_requests_per_hour <= 100):
                raise ValidationError(_('Max requests per hour must be between 1 and 100.'))
