# -*- coding: utf-8 -*-
# Part of gu_email_otp_login. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    otp_login_blocked_group_ids = fields.Many2many(
        related='company_id.otp_login_blocked_group_ids',
        string='Groups Blocked from OTP Login',
        readonly=False,
    )
    otp_code_length = fields.Integer(
        related='company_id.otp_code_length',
        string='OTP Code Length',
        readonly=False,
    )
    otp_validity_minutes = fields.Integer(
        related='company_id.otp_validity_minutes',
        string='OTP Validity (minutes)',
        readonly=False,
    )
    otp_max_attempts = fields.Integer(
        related='company_id.otp_max_attempts',
        string='Max Verification Attempts',
        readonly=False,
    )
    otp_resend_cooldown_seconds = fields.Integer(
        related='company_id.otp_resend_cooldown_seconds',
        string='Resend Cooldown (seconds)',
        readonly=False,
    )
    otp_max_requests_per_hour = fields.Integer(
        related='company_id.otp_max_requests_per_hour',
        string='Max Requests Per Hour',
        readonly=False,
    )
