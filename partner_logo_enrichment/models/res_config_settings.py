# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import requests

from odoo import _, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    logo_dev_api_key = fields.Char(
        string='Logo.dev API Key',
        config_parameter='logo_dev.api_key',
        help='API key/token for Logo.dev service to fetch company logos (e.g. pk_...).',
    )
    logo_fetch_immediate = fields.Boolean(
        string='Immediate Logo Fetch',
        config_parameter='logo_dev.fetch_immediate',
        default=False,
        help='Fetch logos immediately when a partner is created or updated instead of waiting for the scheduled cron job.',
    )

    def action_test_logo_dev_connection(self):
        """Test the configured Logo.dev API key and display a status notification."""
        self.ensure_one()
        params = self.env['ir.config_parameter'].sudo()
        api_key = (self.logo_dev_api_key or params.get_param('logo_dev.api_key') or '').strip()

        if not api_key:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Logo.dev API Key Missing'),
                    'message': _('Please paste your Logo.dev Publishable Key (pk_...) before testing the connection.'),
                    'type': 'warning',
                    'sticky': False,
                },
            }

        # Persist the typed key so the user does not lose it after clicking Test Connection
        params.set_param('logo_dev.api_key', api_key)

        try:
            response = requests.get(
                'https://img.logo.dev/odoo.com',
                params={
                    'token': api_key,
                    'format': 'png',
                    'size': '128',
                },
                timeout=10,
            )
            if response.status_code == 200 and response.content:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Connection Successful'),
                        'message': _('Logo.dev API Key is valid and connected! (%d bytes received)') % len(response.content),
                        'type': 'success',
                        'sticky': False,
                    },
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Logo.dev Connection Failed'),
                    'message': _('Logo.dev returned HTTP %s. Please check that your Publishable Key (pk_...) is valid.') % response.status_code,
                    'type': 'danger',
                    'sticky': False,
                },
            }
        except requests.exceptions.RequestException as exc:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Network Error'),
                    'message': _('Could not reach Logo.dev API: %s') % str(exc),
                    'type': 'danger',
                    'sticky': False,
                },
            }