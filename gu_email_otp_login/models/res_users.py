# -*- coding: utf-8 -*-
# Part of gu_email_otp_login. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, models, _
from odoo.exceptions import AccessDenied, UserError
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    """Extends res.users with:

    1. A lookup helper (`_otp_find_user`) usable from a public/anonymous
       controller context, to resolve a login/email into a user record
       before authentication has happened.
    2. A send helper (`_otp_send`) that issues and emails a fresh OTP.
    3. A `_otp_send_unknown_email_notice` helper that emails a "this
       address isn't registered" notice when the typed email matches no
       account.
    4. A group-based eligibility check (`_otp_is_allowed`) plus a
       `_otp_send_not_allowed_notice` helper for real users who are
       excluded from OTP login by company policy.
    5. A `_check_credentials` override that plugs a new ``otp`` credential
       type into Odoo's standard authentication pipeline - following the
       exact same pattern used by `auth_oauth` and `auth_ldap` in core.

    In every case, the login page's own response never changes based on
    which of these paths ran (see AuthOtpLogin.otp_send) - only the
    content of an email sent to the address itself, which only its real
    owner can ever read, varies.
    """
    _inherit = 'res.users'

    # ------------------------------------------------------------------
    # Lookup / send
    # ------------------------------------------------------------------
    @api.model
    def _otp_find_user(self, login):
        """Resolve ``login`` (typically an email) to a single active user.

        Matches either the ``login`` field (core's default behaviour, via
        `_get_login_domain`) OR the user's actual `email` - the two are
        not always the same value (e.g. Odoo's own demo data: login=
        'demo', email='mark.brown23@example.com'), and our login screen
        asks for "Email" specifically.

        :param str login: the login/email entered by the visitor.
        :rtype: res.users
        """
        Users = self.sudo()
        domain = expression.OR([
            Users._get_login_domain(login),
            [('email', '=', login)],
        ])
        return Users.search(domain, order=Users._get_login_order(), limit=1)

    def _otp_is_allowed(self):
        """Whether this user is permitted to use OTP login, per the
        company's `otp_login_blocked_group_ids` setting.

        This is a block-list, not an allow-list: an empty setting means
        "no restriction" (every user is allowed, matching the module's
        behaviour before this setting existed), and adding a group here
        excludes only that group - everyone else, including any group
        created later, is unaffected. Chosen deliberately over an
        allow-list, since most real instances have many groups and only
        want to exclude a handful (e.g. "Interns"), rather than having
        to enumerate every single group that should keep working.

        :return: True if OTP login is available for this user.
        :rtype: bool
        """
        self.ensure_one()
        blocked_groups = self.company_id.otp_login_blocked_group_ids
        if not blocked_groups:
            return True
        return not bool(self.groups_id & blocked_groups)

    @api.model
    def _otp_get_default_email_from(self):
        """Resolve a sender address using only environment-level context
        (no specific user record available).

        :return: a sender address, or False if none is configured.
        :rtype: str | bool
        """
        email_from = self.env.company.email
        if email_from:
            return email_from

        get_param = self.env['ir.config_parameter'].sudo().get_param
        catchall_domain = get_param('mail.catchall.domain')
        if catchall_domain:
            default_from = get_param('mail.default.from', 'notifications')
            return f'{default_from}@{catchall_domain}'

        return False

    def _otp_get_email_from(self):
        """Resolve a sender address for OTP-related email to this user.

        :return: a sender address, or False if none configured.
        :rtype: str | bool
        """
        self.ensure_one()
        return self.company_id.email or self._otp_get_default_email_from()

    def _otp_send(self):
        """Generate a fresh OTP for this user and email it to them.

        :return: True once the email has been queued for sending.
        :rtype: bool
        :raises UserError: if the user has no email, no sender address
            could be resolved, or the OTP template is missing.
        """
        self.ensure_one()
        if not self.email:
            raise UserError(_('This account has no email address on file, '
                              'so an OTP cannot be sent.'))

        email_from = self._otp_get_email_from()
        if not email_from:
            raise UserError(_(
                'No sender email address is configured. Set an email '
                'address on your company (Settings > General Settings > '
                'Companies), or configure the "Default From Address" / '
                '"Catchall Domain" system parameters, then try again.'
            ))

        _otp_record, plaintext_otp = self.env['res.users.otp']._generate_otp(self)

        template = self.env.ref('gu_email_otp_login.mail_template_otp', raise_if_not_found=False)
        if not template:
            raise UserError(_('The OTP email template is not configured.'))

        template.sudo().with_context(otp_code=plaintext_otp).send_mail(
            self.id,
            force_send=True,
            email_values={'email_to': self.email, 'email_from': email_from},
        )
        _logger.info('OTP requested for user login:%s', self.login)
        return True

    @api.model
    def _otp_send_unknown_email_notice(self, login):
        """Notify ``login`` that no account matches this email.

        :param str login: the email address that matched no account.
        :raises UserError: if no sender address or the template is
            unavailable.
        """
        email_from = self._otp_get_default_email_from()
        if not email_from:
            raise UserError(_('No sender email address is configured.'))

        template = self.env.ref('gu_email_otp_login.mail_template_otp_unknown', raise_if_not_found=False)
        if not template:
            raise UserError(_('The "email not registered" template is not configured.'))

        template.sudo().with_context(attempted_login=login).send_mail(
            self.env.company.id,
            force_send=True,
            email_values={'email_to': login, 'email_from': email_from},
        )
        _logger.info('Sent "not registered" notice for an unmatched login attempt')
        return True

    def _otp_send_not_allowed_notice(self):
        """Notify this user that OTP login isn't available for their
        account, and that they should use their password instead.

        Only ever called for a *real* user excluded by the company's
        group policy (see `_otp_is_allowed`) - never for an unregistered
        email, which uses different, deliberately vaguer wording.

        :raises UserError: if the user has no email, no sender address
            could be resolved, or the notice template is missing.
        """
        self.ensure_one()
        if not self.email:
            raise UserError(_('This account has no email address on file.'))

        email_from = self._otp_get_email_from()
        if not email_from:
            raise UserError(_('No sender email address is configured.'))

        template = self.env.ref('gu_email_otp_login.mail_template_otp_not_allowed', raise_if_not_found=False)
        if not template:
            raise UserError(_('The "OTP not allowed" template is not configured.'))

        template.sudo().send_mail(
            self.id,
            force_send=True,
            email_values={'email_to': self.email, 'email_from': email_from},
        )
        _logger.info('Sent "OTP not allowed" notice for user login:%s', self.login)
        return True

    # ------------------------------------------------------------------
    # Authentication pipeline integration
    # ------------------------------------------------------------------
    def _check_credentials(self, credential, env):
        """Extend credential validation to support the ``otp`` login type.

        :param dict credential: expected shape for OTP login is
            ``{'login': <email>, 'otp': <6-digit code>, 'type': 'otp'}``.
        :param dict env: the ``user_agent_env`` dict passed down the
            authentication pipeline.
        """
        try:
            return super()._check_credentials(credential, env)
        except AccessDenied:
            if credential.get('type') != 'otp':
                raise

            otp = credential.get('otp')
            if not otp:
                raise

            otp_record = self.env['res.users.otp'].sudo().search([
                ('user_id', '=', self.env.user.id),
                ('state', '=', 'pending'),
            ], order='create_date desc', limit=1)

            if not otp_record:
                raise AccessDenied(_('No pending OTP found for this account. '
                                     'Please request a new one.'))

            # Re-check group eligibility here too, not just at send time:
            # if an admin removes this user from an allowed group while
            # their OTP is still within its validity window, they should
            # not be able to complete login on that technicality.
            if not self.env.user._otp_is_allowed():
                raise AccessDenied(_('OTP login is not available for this account. '
                                     'Please use your password instead.'))

            otp_record._verify(otp)  # raises AccessDenied on failure/expiry

            return {
                'uid': self.env.user.id,
                'auth_method': 'otp',
                'mfa': 'default',
            }
