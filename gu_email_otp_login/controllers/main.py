# -*- coding: utf-8 -*-
# Part of gu_email_otp_login. See LICENSE file for full copyright and licensing details.

import logging

from odoo import http, _
from odoo.exceptions import AccessDenied, UserError
from odoo.http import request

from odoo.addons.web.controllers.utils import ensure_db, _get_login_redirect_url

_logger = logging.getLogger(__name__)


class AuthOtpLogin(http.Controller):
    """Password-less, email-OTP based login flow.

    Implemented as three *separate* routes rather than by hijacking
    ``/web/login`` itself:

    1. ``GET  /web/login/otp``          - ask for the email address.
    2. ``POST /web/login/otp/send``     - generate + email the OTP, show
                                           the "enter code" step.
    3. ``POST /web/login/otp/verify``   - verify the OTP and log in.
    """

    # ------------------------------------------------------------------
    # Step 1: ask for the email address
    # ------------------------------------------------------------------
    @http.route('/web/login/otp', type='http', auth='public', methods=['GET'],
                website=False, sitemap=False)
    def otp_request(self, login=None, redirect=None, **kw):
        """Render the "enter your email" step of the OTP login flow."""
        ensure_db()
        if request.session.uid:
            return request.redirect(redirect or '/odoo')

        values = {
            'login': login or '',
            'redirect': redirect,
        }
        return request.render('gu_email_otp_login.otp_request_template', values)

    # ------------------------------------------------------------------
    # Step 2: generate + send the OTP, move to the "enter code" step
    # ------------------------------------------------------------------
    @http.route('/web/login/otp/send', type='http', auth='public', methods=['POST'],
                website=False, sitemap=False, csrf=True)
    def otp_send(self, login=None, redirect=None, **kw):
        ensure_db()
        login = (login or '').strip()
        values = {'login': login, 'redirect': redirect}

        if not login:
            values['error'] = _('Please enter your email address.')
            return request.render('gu_email_otp_login.otp_request_template', values)

        user = request.env['res.users'].sudo()._otp_find_user(login)
        if user and user.sudo()._otp_is_allowed():
            try:
                user.sudo()._otp_send()
            except UserError as exc:
                _logger.warning('OTP send failed for a known login: %s', exc)
        elif user:
            RestrictedLog = request.env['auth.otp.restricted.login'].sudo()
            if RestrictedLog._get_resend_wait_seconds(login, company=user.company_id) == 0:
                try:
                    user.sudo()._otp_send_not_allowed_notice()
                except UserError as exc:
                    _logger.warning('Not-allowed notice failed: %s', exc)
                RestrictedLog._log_attempt(login)
        else:
            UnknownLog = request.env['auth.otp.unregistered.login'].sudo()
            if UnknownLog._get_resend_wait_seconds(login) == 0:
                try:
                    request.env['res.users'].sudo()._otp_send_unknown_email_notice(login)
                except UserError as exc:
                    _logger.warning('Unregistered-email notice failed: %s', exc)
                UnknownLog._log_attempt(login)

        values['message'] = _('If an account exists for %s, a login code has been sent to it.') % login
        values['resend_wait_seconds'] = self._otp_resend_wait_for(login)
        values['otp_code_length'] = self._otp_code_length_for(login)
        return request.render('gu_email_otp_login.otp_verify_template', values)

    # ------------------------------------------------------------------
    # Step 3: verify the OTP and log the user in
    # ------------------------------------------------------------------
    @http.route('/web/login/otp/verify', type='http', auth='public', methods=['POST'],
                website=False, sitemap=False, csrf=True)
    def otp_verify(self, login=None, otp=None, redirect=None, **kw):
        ensure_db()
        login = (login or '').strip()
        values = {'login': login, 'redirect': redirect}

        if not login or not otp:
            values['error'] = _('Please enter the code sent to your email.')
            values['resend_wait_seconds'] = self._otp_resend_wait_for(login)
            values['otp_code_length'] = self._otp_code_length_for(login)
            return request.render('gu_email_otp_login.otp_verify_template', values)

        credential = {'login': login, 'otp': otp.strip(), 'type': 'otp'}
        try:
            auth_info = request.session.authenticate(request.db, credential)
        except AccessDenied as exc:
            values['error'] = exc.args[0] if exc.args else _('Invalid or expired code. Please try again.')
            values['resend_wait_seconds'] = self._otp_resend_wait_for(login)
            values['otp_code_length'] = self._otp_code_length_for(login)
            return request.render('gu_email_otp_login.otp_verify_template', values)

        request.params['login_success'] = True
        return request.redirect(_get_login_redirect_url(auth_info['uid'], redirect=redirect))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _otp_resend_wait_for(login):
        """Seconds left before ``login`` may trigger a new send (a real
        OTP, or one of the two notice emails), or 0 if none is in
        progress.

        Checks whichever of the three tracking models actually applies
        to this login, using each one's own company-configured limits.
        """
        Users = request.env['res.users'].sudo()
        user = Users._otp_find_user(login)
        if user and user._otp_is_allowed():
            return request.env['res.users.otp'].sudo()._get_resend_wait_seconds(user)
        elif user:
            return request.env['auth.otp.restricted.login'].sudo()._get_resend_wait_seconds(
                login, company=user.company_id)
        else:
            return request.env['auth.otp.unregistered.login'].sudo()._get_resend_wait_seconds(login)

    @staticmethod
    def _otp_code_length_for(login):
        """The OTP code length to show in the "enter code" field's
        placeholder/maxlength for ``login``.

        For a known, allowed user, this is their own company's real
        configured length. For an unknown or restricted login, no real
        code exists, so the current default company's setting is used
        purely as a cosmetic default for the input.
        """
        Users = request.env['res.users'].sudo()
        user = Users._otp_find_user(login)
        company = user.company_id if (user and user._otp_is_allowed()) else request.env.company
        return company.otp_code_length
